"""Render the static site from data/ and briefings/."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from augurai.config import Settings
from augurai.domain.ecosystem import rising
from augurai.mdhtml import render_markdown
from augurai.models import (
    Category,
    Entity,
    JobSnapshot,
    Model,
    Person,
    Practice,
    RunRecord,
    SourceHealth,
)
from augurai.site.charts import line_chart_svg
from augurai.store import Store

HERE = Path(__file__).parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"
CATEGORIES: list[Category] = [
    "coding",
    "agentic",
    "reasoning",
    "long_context",
    "multimodal",
    "speed",
    "cost_efficiency",
    "open_weights",
]
ECOSYSTEM_KINDS = [
    ("repo", "Rising repos"),
    ("skill", "Rising skills"),
    ("agent", "Rising agents"),
    ("mcp", "Newest MCP servers"),
]
ECOSYSTEM_LIMIT = 15
RISING_PEOPLE_LIMIT = 20
CHART_KEYWORDS = 5
JOB_MARKETS = [("global", "Global / remote"), ("fr", "France")]
ARCHIVE_LIMIT = 365
NAV = [
    ("today", "Today", ""),
    ("models", "Models", "models/"),
    ("ecosystem", "Ecosystem", "ecosystem/"),
    ("people", "People", "people/"),
    ("playbook", "Playbook", "playbook/"),
    ("jobs", "Jobs", "jobs/"),
    ("archive", "Archive", "archive/"),
    ("about", "About", "about/"),
]


def safe_url(url: str) -> str:
    """Allow only http(s) links; anything else (javascript:, data:, ...) becomes a dead link."""
    return url if urlsplit(url).scheme.lower() in ("http", "https") else "#"


def _score(model: Model, key: str) -> float | None:
    for scores in model.scores.values():
        if key in scores:
            return scores[key]
    return None


def _model_sort_key(model: Model) -> tuple[float, int, str]:
    released = model.released.toordinal() if model.released else 0
    return (-(_score(model, "intelligence") or -1.0), -released, model.name.lower())


def _updated(runs: list[RunRecord], tz: str) -> str:
    if not runs:
        return "Not updated yet"
    latest = max(runs, key=lambda r: r.started).started.astimezone(ZoneInfo(tz))
    return f"Updated {latest:%Y-%m-%d %H:%M} ({tz})"


def _job_markets(jobs: list[JobSnapshot]) -> list[dict]:
    markets = []
    for market, label in JOB_MARKETS:
        snaps = [j for j in jobs if j.market == market]
        if not snaps:
            continue
        months = sorted({j.month for j in snaps})
        totals: dict[str, dict[str, int]] = {}
        sources: dict[str, set[str]] = {}
        for snap in snaps:
            sources.setdefault(snap.month, set()).add(snap.source)
            for keyword, n in snap.keyword_counts.items():
                totals.setdefault(keyword, {}).setdefault(snap.month, 0)
                totals[keyword][snap.month] += n
        ranked = sorted(totals, key=lambda k: (-totals[k].get(months[-1], 0), k))
        rows = [{"keyword": k, "counts": [totals[k].get(m, 0) for m in months]} for k in ranked]
        series = {k: [float(totals[k].get(m, 0)) for m in months] for k in ranked[:CHART_KEYWORDS]}
        markets.append(
            {
                "label": label,
                "months": months,
                "rows": rows,
                "chart": Markup(
                    line_chart_svg(series, months, f"{label}: keyword demand by month")
                ),
                "sources": sorted({s for srcs in sources.values() for s in srcs}),
                "roles": sorted(
                    {r for s in snaps if s.month == months[-1] for r in s.notable_roles}
                )[:8],
            }
        )
    return markets


def build_site(root: Path, out: Path, settings: Settings) -> list[Path]:
    store = Store(root / "data")
    models = sorted(store.read("models", Model), key=_model_sort_key)
    entities = store.read_map("entities", Entity)
    people = store.read("people", Person)
    practices = store.read("practices", Practice)
    jobs = store.read("jobs", JobSnapshot)
    health = store.read("health", SourceHealth)
    runs = store.read("runs", RunRecord)
    briefing_files = sorted((root / "briefings").glob("*.md"), reverse=True)[:ARCHIVE_LIMIT]
    briefings = [(p.stem, p.read_text(encoding="utf-8")) for p in briefing_files]

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_url"] = safe_url
    base = settings.site_base_path
    common = {
        "base": base,
        "settings": settings,
        "updated": _updated(runs, settings.timezone),
        "nav": NAV,
        "score": _score,
    }
    written: list[Path] = []

    def render(template: str, target: str, page: str, **context: object) -> None:
        html = env.get_template(template).render(page=page, **common, **context)
        path = out / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        written.append(path)

    def as_html(markdown: str) -> Markup:
        return Markup(render_markdown(markdown))

    latest = briefings[0] if briefings else None
    render(
        "index.html",
        "index.html",
        "today",
        briefing_html=as_html(latest[1]) if latest else None,
        briefing_day=latest[0] if latest else None,
        counts={"models": len(models), "projects": len(entities), "people": len(people)},
    )
    render("models.html", "models/index.html", "models", models=models, categories=CATEGORIES)
    for model in models:
        render("model.html", f"models/{model.id}/index.html", "models", model=model)

    today = (
        max((r.started.date() for r in runs), default=None) or datetime.now(ZoneInfo("UTC")).date()
    )
    groups = []
    for kind, label in ECOSYSTEM_KINDS:
        ids = rising(entities, kind, ECOSYSTEM_LIMIT, today)
        groups.append({"label": label, "kind": kind, "entries": [entities[i] for i in ids]})
    render("ecosystem.html", "ecosystem/index.html", "ecosystem", groups=groups)

    by_status = {
        s: [p for p in people if p.status == s] for s in ("seed", "followed", "rising", "dormant")
    }
    by_status["rising"] = sorted(by_status["rising"], key=lambda p: -p.score)[:RISING_PEOPLE_LIMIT]
    render("people.html", "people/index.html", "people", groups=by_status)

    names = {p.id: p.name for p in people}
    practices = sorted(practices, key=lambda p: (-len(p.reinforced_by), p.title.lower()))
    render(
        "playbook.html",
        "playbook/index.html",
        "playbook",
        practices=practices,
        names=names,
        tags=sorted({t for p in practices for t in p.tags}),
        authors=sorted({names.get(p.person_id, p.person_id) for p in practices}),
    )
    render("jobs.html", "jobs/index.html", "jobs", markets=_job_markets(jobs))
    render("archive.html", "archive/index.html", "archive", days=[d for d, _ in briefings])
    for day, text in briefings:
        render("briefing.html", f"archive/{day}/index.html", "archive", day=day, body=as_html(text))
    render(
        "about.html",
        "about/index.html",
        "about",
        health=sorted(health, key=lambda h: h.id),
        runs=runs[-10:],
    )

    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    practices_path = data_dir / "practices.json"
    practices_path.write_text(
        json.dumps([p.model_dump(mode="json") for p in practices], indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    written.append(practices_path)
    shutil.copytree(STATIC, out / "static", dirs_exist_ok=True)
    written += [out / "static" / f.name for f in STATIC.iterdir()]
    return written
