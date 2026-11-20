import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from augurai.models import (
    Entity,
    JobSnapshot,
    Model,
    Person,
    Practice,
    RunRecord,
    SourceHealth,
    WorkItem,
)
from augurai.site.build import build_site
from augurai.store import Store

TODAY = date(2026, 11, 20)
BASE = "/Augurai/"
HREF = re.compile(r'(?:href|src)="(' + re.escape(BASE) + r'[^"#?]*)')


def internal_links(site: Path) -> set[str]:
    links: set[str] = set()
    for page in site.rglob("*.html"):
        links.update(HREF.findall(page.read_text(encoding="utf-8")))
    return links


def target_exists(site: Path, link: str) -> bool:
    rel = link[len(BASE) :]
    path = site / rel
    return (path / "index.html").exists() if (rel == "" or rel.endswith("/")) else path.exists()


@pytest.fixture
def populated_root(tmp_path):
    store = Store(tmp_path / "data")
    store.write(
        "models",
        [
            Model(
                id="opus",
                name="Claude Opus",
                provider="anthropic",
                released=TODAY,
                first_seen=TODAY,
                context_window=1_000_000,
                price_in=5.0,
                price_out=25.0,
                scores={"artificial-analysis": {"intelligence": 72.5, "coding": 70.0}},
                best_at=["coding", "long_context"],
                use_cases=["Large refactors"],
                avoid_for=["Cheap bulk work"],
                links={"openrouter": "https://openrouter.ai/anthropic/claude-opus"},
            ),
            Model(id="tiny", name="Tiny", provider="acme", first_seen=TODAY),
        ],
    )
    store.write(
        "entities",
        [
            Entity(
                id="e1",
                kind="repo",
                name="o/hot",
                url="https://github.com/o/hot",
                owner="o",
                stars=500,
                velocity_7d=12.5,
                description="<script>alert('x')</script> hot repo",
                first_seen=TODAY,
            ),
            Entity(
                id="e2",
                kind="mcp",
                name="Some server",
                url="https://example.com/mcp",
                owner="acme",
                first_seen=TODAY,
            ),
        ],
    )
    store.write(
        "people",
        [
            Person(
                id="matt-pocock",
                name="Matt Pocock",
                status="seed",
                why_follow="Small workflows",
                what_to_learn="Grill first",
                links={"github": "https://github.com/mattpocock"},
                recent_work=[
                    WorkItem(title="Plan then build", url="https://x/w", person_id="matt-pocock")
                ],
            ),
            Person(id="newdev", name="newdev", status="rising", score=6.0),
        ],
    )
    store.write(
        "practices",
        [
            Practice(
                id="grill-first",
                title="Grill the idea",
                principle="Interrogate before building",
                how_to_apply="Run /grill-me",
                person_id="matt-pocock",
                source_url="https://x/w",
                tags=["planning"],
                first_seen=TODAY,
            )
        ],
    )
    store.write(
        "jobs",
        [
            JobSnapshot(
                id=f"global-jobs-hn-{m}",
                month=m,
                market="global",
                source="jobs-hn",
                total_posts=100,
                keyword_counts={"LLM": n, "RAG": n // 2},
            )
            for m, n in (("2026-10", 30), ("2026-11", 45))
        ],
    )
    store.write(
        "health",
        [SourceHealth(id="openrouter", last_success=datetime(2026, 11, 20, 5, tzinfo=UTC))],
    )
    store.write(
        "runs",
        [
            RunRecord(
                id="r1",
                started=datetime(2026, 11, 20, 4, 30, tzinfo=UTC),
                mode="morning",
                email_sent=True,
            )
        ],
    )
    briefings = tmp_path / "briefings"
    briefings.mkdir()
    (briefings / "2026-11-19.md").write_text("# Yesterday\n\n- old news\n", encoding="utf-8")
    (briefings / "2026-11-20.md").write_text(
        "# Opus takes coding\n\n- [Hot](https://github.com/o/hot)\n", encoding="utf-8"
    )
    return tmp_path


def test_all_pages_render_and_links_resolve(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    pages = build_site(populated_root, site, settings)
    assert pages
    for expected in (
        "index.html",
        "models/index.html",
        "models/opus/index.html",
        "ecosystem/index.html",
        "people/index.html",
        "playbook/index.html",
        "jobs/index.html",
        "archive/index.html",
        "archive/2026-11-20/index.html",
        "about/index.html",
        "static/site.css",
        "static/filter.js",
    ):
        assert (site / expected).exists(), expected
    for link in internal_links(site):
        assert target_exists(site, link), link


def test_index_shows_latest_briefing_and_update_time(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "Opus takes coding" in index and "Yesterday" not in index
    assert "Updated 2026-11-20 05:30" in index  # 04:30 UTC is 05:30 in Tunis


def test_models_table_has_filterable_rows(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "models/index.html").read_text(encoding="utf-8")
    assert 'data-category="coding long_context"' in html and "Claude Opus" in html
    detail = (site / "models/opus/index.html").read_text(encoding="utf-8")
    assert "Large refactors" in detail and "Cheap bulk work" in detail


def test_empty_data_still_builds(tmp_path, settings):
    site = tmp_path / "_site"
    build_site(tmp_path / "empty", site, settings)
    assert "No briefing yet" in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "models/index.html").exists() and (site / "jobs/index.html").exists()


def test_practices_json_exported(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    data = json.loads((site / "data/practices.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in data] == ["grill-first"]


def test_untrusted_text_is_escaped(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "ecosystem/index.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html and "&lt;script&gt;alert" in html


def test_jobs_page_has_svg_chart_attribution_and_table(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "jobs/index.html").read_text(encoding="utf-8")
    assert "<svg" in html and "LLM" in html
    assert "https://remoteok.com/" in html


def test_about_credits_artificial_analysis_and_shows_health(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "about/index.html").read_text(encoding="utf-8")
    assert "https://artificialanalysis.ai/" in html and "openrouter" in html


def test_people_page_groups_and_limits_rising(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "people/index.html").read_text(encoding="utf-8")
    assert "Matt Pocock" in html and "Grill first" in html and "newdev" in html
    assert "Plan then build" in html


def test_unsafe_urls_never_become_links(tmp_path, populated_root, settings):
    store = Store(populated_root / "data")
    entities = store.read("entities", Entity)
    entities.append(
        Entity(
            id="e3",
            kind="repo",
            name="evil",
            url="javascript:alert(1)",
            owner="x",
            first_seen=TODAY,
        )
    )
    store.write("entities", entities)
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    html = (site / "ecosystem/index.html").read_text(encoding="utf-8")
    assert "javascript:" not in html.lower()


def page(site, name):
    return (site / name).read_text(encoding="utf-8")


def built(tmp_path, populated_root, settings):
    site = tmp_path / "_site"
    build_site(populated_root, site, settings)
    return site


def test_models_page_has_search_sort_count_and_monograms(tmp_path, populated_root, settings):
    html = page(built(tmp_path, populated_root, settings), "models/index.html")
    assert 'type="search"' in html and "data-filter-text" in html
    assert 'data-sort="models"' in html and "data-count" in html
    assert 'data-text="claude opus anthropic' in html  # searchable text per row
    assert 'data-sort-intelligence="72.5"' in html
    assert 'class="mono"' in html  # provider monogram
    assert "<label" in html  # every control is labelled


def test_people_page_shows_github_avatars_and_search(tmp_path, populated_root, settings):
    html = page(built(tmp_path, populated_root, settings), "people/index.html")
    assert "https://github.com/mattpocock.png" in html and 'loading="lazy"' in html
    assert "data-filter-text" in html


def test_ecosystem_has_section_jump_links_search_and_owner_avatars(
    tmp_path, populated_root, settings
):
    html = page(built(tmp_path, populated_root, settings), "ecosystem/index.html")
    assert 'href="#repo"' in html and 'id="repo"' in html
    assert "https://github.com/o.png" in html and "data-filter-text" in html


def test_every_page_has_a_theme_toggle_and_skip_link(tmp_path, populated_root, settings):
    site = built(tmp_path, populated_root, settings)
    for name in ("index.html", "models/index.html", "jobs/index.html", "about/index.html"):
        html = page(site, name)
        assert 'id="theme-toggle"' in html and 'class="skip"' in html


def test_home_page_has_a_side_panel_with_newest_models_and_rising_projects(
    tmp_path, populated_root, settings
):
    html = page(built(tmp_path, populated_root, settings), "index.html")
    assert "Newest models" in html and "Rising now" in html
    assert "/Augurai/models/opus/" in html and "o/hot" in html


def test_playbook_shows_the_exercise_when_there_is_one(tmp_path, populated_root, settings):
    store = Store(populated_root / "data")
    practices = store.read("practices", Practice)
    practices[0] = practices[0].model_copy(
        update={"exercise": "Grill your next idea for ten minutes"}
    )
    store.write("practices", practices)
    html = page(built(tmp_path, populated_root, settings), "playbook/index.html")
    assert "Try it yourself" in html and "Grill your next idea for ten minutes" in html


def test_about_page_explains_how_to_learn_with_ai(tmp_path, populated_root, settings):
    html = page(built(tmp_path, populated_root, settings), "about/index.html")
    assert "Learning with AI" in html and "predict" in html.lower()
