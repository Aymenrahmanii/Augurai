"""Build the morning briefing, from Claude's text when available and deterministically otherwise."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from augurai.config import Settings
from augurai.domain.changes import Changes
from augurai.enrich import BriefingText
from augurai.models import Entity, JobSnapshot, Model, Person
from augurai.store import Store

RISING_LABELS = {
    "repo": "Rising repos",
    "skill": "Rising skills",
    "mcp": "Rising MCP servers",
    "agent": "Rising agents",
}
LIST_LIMIT = 5
WORK_LIMIT = 10
JOB_KEYWORDS_SHOWN = 5
TOKEN_HINT = (
    "If the Claude token expired: run `claude setup-token` and update the "
    "`CLAUDE_CODE_OAUTH_TOKEN` repository secret."
)


@dataclass
class Briefing:
    day: date
    headline: str
    markdown: str
    enriched: bool


@dataclass
class _Data:
    models: dict[str, Model]
    entities: dict[str, Entity]
    people: dict[str, Person]
    jobs: list[JobSnapshot]


def _load(store: Store) -> _Data:
    return _Data(
        models=store.read_map("models", Model),
        entities=store.read_map("entities", Entity),
        people=store.read_map("people", Person),
        jobs=store.read("jobs", JobSnapshot),
    )


def _headline(changes: Changes, data: _Data) -> str:
    if changes.first_run:
        return (
            f"Baseline established: Augurai is now tracking {len(data.models)} models, "
            f"{len(data.entities)} projects and {len(data.people)} people."
        )
    rising = sum(len(ids) for ids in changes.rising.values())
    parts = [
        (len(changes.new_models), "new model(s)"),
        (len(changes.benchmark_moves), "benchmark move(s)"),
        (rising, "rising project(s)"),
        (len(changes.promoted), "new person/people to follow"),
    ]
    text = ", ".join(f"{n} {label}" for n, label in parts if n)
    return text or "Quiet day: nothing major changed"


def _what_changed(changes: Changes, data: _Data) -> str:
    lines: list[str] = []
    if changes.new_models:
        names = [data.models[m].name if m in data.models else m for m in changes.new_models]
        lines.append("- **New models:** " + ", ".join(names))
    for move in changes.benchmark_moves:
        name = data.models[move.model_id].name if move.model_id in data.models else move.model_id
        category = move.category.replace("_", " ")
        verb = "entered" if move.change == "entered" else "left"
        lines.append(f"- {name} {verb} the top 3 for {category}")
    for kind, label in RISING_LABELS.items():
        entities = [
            data.entities[i]
            for i in changes.rising.get(kind, [])[:LIST_LIMIT]
            if i in data.entities
        ]
        if entities:
            links = ", ".join(f"[{e.name}]({e.url})" for e in entities)
            lines.append(f"- **{label}:** {links}")
    if changes.promoted:
        names = [data.people[p].name if p in data.people else p for p in changes.promoted]
        lines.append("- **Now following:** " + ", ".join(names))
    if changes.demoted:
        names = [data.people[p].name if p in data.people else p for p in changes.demoted]
        lines.append("- **Gone quiet:** " + ", ".join(names))
    return "\n".join(lines) or "- Nothing new since the last briefing."


def _people_section(changes: Changes, data: _Data) -> str:
    lines = []
    for work in changes.people_work[:WORK_LIMIT]:
        person = data.people.get(work.person_id)
        who = person.name if person else work.person_id
        lines.append(f"- [{work.title}]({work.url}) ({who})")
    return "\n".join(lines) or "- No new posts from the people you follow."


def _jobs_pulse(data: _Data) -> str | None:
    if not data.jobs:
        return None
    month = max(j.month for j in data.jobs)
    lines = []
    for market in ("global", "fr"):
        counts: dict[str, int] = {}
        for snap in (j for j in data.jobs if j.month == month and j.market == market):
            for keyword, n in snap.keyword_counts.items():
                counts[keyword] = counts.get(keyword, 0) + n
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:JOB_KEYWORDS_SHOWN]
        if top and any(n for _, n in top):
            label = {"global": "Global / remote", "fr": "France"}[market]
            lines.append(f"- **{label}** ({month}): " + " · ".join(f"{k} {n}" for k, n in top))
    return "\n".join(lines) or None


def _footer(
    changes: Changes, text: BriefingText | None, note: str | None, settings: Settings
) -> str:
    lines = ["---", ""]
    if text is None:
        lines.append(
            f"Summaries unavailable today: {note}" if note else "Summaries unavailable today."
        )
        lines.append(TOKEN_HINT)
    elif note:
        lines.append(f"Enrichment note: {note}")
    if changes.failing_sources:
        lines.append("Sources failing 3+ runs: " + ", ".join(changes.failing_sources))
    lines.append(f"[Open Augurai]({settings.site_url})")
    return "\n\n".join(lines)


def build(
    changes: Changes,
    store: Store,
    text: BriefingText | None,
    enrichment_note: str | None,
    settings: Settings,
) -> Briefing:
    data = _load(store)
    sections: list[tuple[str, str]] = []
    if text is not None:
        headline = text.headline
        sections = [(s.title, s.body_md) for s in text.sections]
        if not any("practice" in title.lower() for title, _ in sections):
            sections.append(("One practice to try today", text.practice_of_the_day))
    else:
        headline = _headline(changes, data)
        sections = [
            ("What changed", _what_changed(changes, data)),
            ("From the people you follow", _people_section(changes, data)),
        ]
    if changes.day.weekday() == 0 and (pulse := _jobs_pulse(data)):
        sections.append(("Jobs pulse", pulse))
    body = "\n\n".join(f"## {title}\n\n{content}" for title, content in sections)
    markdown = f"# {headline}\n\n{body}\n\n{_footer(changes, text, enrichment_note, settings)}\n"
    return Briefing(
        day=changes.day, headline=headline, markdown=markdown, enriched=text is not None
    )


def save(briefing: Briefing, root: Path) -> Path:
    path = root / "briefings" / f"{briefing.day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(briefing.markdown, encoding="utf-8")
    return path
