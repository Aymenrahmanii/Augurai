"""Cloud pipeline orchestration: collect (deterministic) now, finish after enrichment."""

import json
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import httpx

from augurai.briefing import build as build_briefing
from augurai.briefing import save as save_briefing
from augurai.config import Settings
from augurai.domain.catalog import compute_best_at, merge_models
from augurai.domain.changes import Changes, Snapshot, compute, merge_changes
from augurai.domain.ecosystem import merge_entities, rising
from augurai.domain.jobs import merge_snapshots, snapshot
from augurai.domain.people import attach_work, candidate_signals, seed, update_discovery
from augurai.enrich import BriefingText, EnrichInput, EnrichStatus, merge, prepare
from augurai.models import Entity, JobSnapshot, Model, Person, RunRecord, SourceHealth
from augurai.site.build import build_site
from augurai.sources import all_sources
from augurai.sources.base import (
    Source,
    SourceContext,
    github_headers,
    make_client,
    run_sources,
)
from augurai.store import Store
from augurai.timeutil import local_date

Mode = Literal["morning", "refresh"]
ENTITY_KINDS = ("repo", "skill", "mcp", "agent")
BEST_AT_TOP_N = 3
MAX_RUN_RECORDS = 200


def collect(
    root: Path,
    settings: Settings,
    mode: Mode,
    now: datetime,
    sources: Sequence[Source] | None = None,
    env: Mapping[str, str] | None = None,
    http: httpx.Client | None = None,
) -> Changes:
    store = Store(root / "data")
    today = local_date(now, settings.timezone)
    models = store.read_map("models", Model)
    entities = store.read_map("entities", Entity)
    people = seed(store.read_map("people", Person), settings)
    jobs = store.read_map("jobs", JobSnapshot)
    health = store.read_map("health", SourceHealth)
    before = Snapshot(dict(models), dict(entities), dict(people))

    followed = [p for p in people.values() if p.status == "followed"]
    active_sources = list(sources) if sources is not None else all_sources(settings, followed)
    ctx = SourceContext(
        settings=settings,
        http=http or make_client(),
        now=now,
        env=env if env is not None else os.environ,
    )
    run = run_sources(active_sources, ctx, health)

    models = compute_best_at(
        merge_models(models, [i for i in run.items if i.kind == "model"], today), BEST_AT_TOP_N
    )
    entities = merge_entities(entities, [i for i in run.items if i.kind in ENTITY_KINDS], today)
    rising_by_kind = {k: rising(entities, k, settings.rising_top_n, today) for k in ENTITY_KINDS}
    people = attach_work(people, run.items)
    signals = candidate_signals(
        run.items, entities, [eid for ids in rising_by_kind.values() for eid in ids], today
    )
    known_users = {e.owner.lower() for e in entities.values() if e.owner_type == "User"}
    people, promoted, demoted = update_discovery(
        people, signals, today, settings, is_user=_user_check(ctx, known_users)
    )
    job_items = [i for i in run.items if i.kind == "job"]
    if job_items:
        month = f"{today:%Y-%m}"
        jobs = merge_snapshots(jobs, snapshot(job_items, month, settings.job_keywords))

    store.write("models", models.values())
    store.write("entities", entities.values())
    store.write("people", people.values())
    store.write("jobs", jobs.values())
    store.write("health", run.health.values())

    changes = compute(
        before,
        Snapshot(models, entities, people),
        run,
        today,
        rising=rising_by_kind,
        promoted=promoted,
        demoted=demoted,
    )
    # The briefing must cover everything since the last briefing, not just this run's diff.
    pending = merge_changes(load_pending(store.root, today), changes)
    save_pending(store.root, pending)
    work = root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "changes.json").write_text(pending.model_dump_json(indent=2), encoding="utf-8")
    items = [i.model_dump(mode="json") for i in run.items if i.kind != "job"]
    (work / "items.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    run_info = {
        "started": now.isoformat(),
        "mode": mode,
        "sources_ok": run.ok,
        "sources_failed": run.failed,
        "sources_skipped": run.skipped,
    }
    (work / "run.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    if mode == "morning":
        prepare(store, pending, run.items, settings, work / "enrich_input.json")
    return changes


PENDING_FILE = "pending_changes.json"


def load_pending(data_dir: Path, today: date) -> Changes:
    path = data_dir / PENDING_FILE
    if path.exists():
        try:
            return Changes.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            pass  # a corrupt accumulator must not stop the pipeline; start over
    return Changes(day=today)


def save_pending(data_dir: Path, changes: Changes) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(changes.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    (data_dir / PENDING_FILE).write_text(text, encoding="utf-8", newline="\n")


def _user_check(ctx: SourceContext, known_users: set[str]) -> Callable[[str], bool]:
    """True when a GitHub login is a person; organisations and unknown accounts are rejected."""
    cache: dict[str, bool] = {}

    def check(login: str) -> bool:
        key = login.lower()
        if key in known_users:
            return True
        if key not in cache:
            try:
                response = ctx.http.get(
                    f"https://api.github.com/users/{login}", headers=github_headers(ctx.env)
                )
                cache[key] = response.status_code == 200 and response.json().get("type") == "User"
            except (httpx.HTTPError, ValueError):
                cache[key] = False
        return cache[key]

    return check


def _load_changes(path: Path, today: date) -> Changes:
    if path.exists():
        return Changes.model_validate_json(path.read_text(encoding="utf-8"))
    return Changes(day=today)


def _load_run_info(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _enrich(
    store: Store, work: Path, today: date
) -> tuple[EnrichStatus, str | None, BriefingText | None]:
    input_path = work / "enrich_input.json"
    if not input_path.exists():
        return "skipped", None, None
    enrich_input = EnrichInput.model_validate_json(input_path.read_text(encoding="utf-8"))
    status, note, text = merge(store, work / "enrich_output.json", enrich_input, today)
    if status == "skipped":  # input was prepared, so a missing output means the Claude step failed
        return "failed", "Claude step did not produce output", None
    return status, note, text


def finish(root: Path, settings: Settings, mode: Mode, now: datetime) -> RunRecord:
    store = Store(root / "data")
    today = local_date(now, settings.timezone)
    work = root / "work"
    changes = _load_changes(work / "changes.json", today)
    info = _load_run_info(work / "run.json")

    enrichment: EnrichStatus = "skipped"
    note: str | None = None
    briefing_written = False
    if mode == "morning":
        enrichment, note, text = _enrich(store, work, today)
        # One briefing per local day: a later run must never replace a good one with an empty one.
        if not (root / "briefings" / f"{today.isoformat()}.md").exists():
            save_briefing(build_briefing(changes, store, text, note, settings), root)
            save_pending(store.root, Changes(day=today))  # everything pending is now reported
            briefing_written = True

    record = RunRecord(
        id=now.isoformat(),
        started=now,
        mode=mode,
        sources_ok=info.get("sources_ok", []),
        sources_failed=info.get("sources_failed", []),
        sources_skipped=info.get("sources_skipped", []),
        enrichment=enrichment,
        enrichment_note=note,
        briefing_written=briefing_written,
    )
    runs = sorted([*store.read("runs", RunRecord), record], key=lambda r: r.id)
    store.write("runs", runs[-MAX_RUN_RECORDS:])
    build_site(root, root / "_site", settings)
    return record
