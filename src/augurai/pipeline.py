"""Cloud pipeline orchestration: collect (deterministic) now, finish after enrichment."""

import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx

from augurai.config import Settings
from augurai.domain.catalog import compute_best_at, merge_models
from augurai.domain.changes import Changes, Snapshot, compute
from augurai.domain.ecosystem import merge_entities, rising
from augurai.domain.jobs import merge_snapshots, snapshot
from augurai.domain.people import attach_work, candidate_signals, seed, update_discovery
from augurai.models import Entity, JobSnapshot, Model, Person, SourceHealth
from augurai.sources import all_sources
from augurai.sources.base import Source, SourceContext, make_client, run_sources
from augurai.store import Store
from augurai.timeutil import local_date

Mode = Literal["morning", "refresh"]
ENTITY_KINDS = ("repo", "skill", "mcp", "agent")
BEST_AT_TOP_N = 3


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
        run.items, entities, [eid for ids in rising_by_kind.values() for eid in ids]
    )
    people, promoted, demoted = update_discovery(people, signals, today, settings)
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
    work = root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "changes.json").write_text(changes.model_dump_json(indent=2), encoding="utf-8")
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
    return changes
