from datetime import date

import pytest

from augurai.briefing import Briefing, build, save
from augurai.domain.changes import BenchmarkMove, Changes
from augurai.enrich import BriefingSection, BriefingText
from augurai.models import Entity, JobSnapshot, Model, Person, WorkItem
from augurai.store import Store

FRIDAY = date(2026, 11, 20)
MONDAY = date(2026, 11, 23)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "data")
    s.write(
        "models",
        [
            Model(id="opus", name="Claude Opus", provider="anthropic", first_seen=FRIDAY),
            Model(id="gpt", name="GPT X", provider="openai", first_seen=FRIDAY),
        ],
    )
    s.write(
        "entities",
        [
            Entity(
                id="e1",
                kind="repo",
                name="o/hot",
                url="https://github.com/o/hot",
                owner="o",
                first_seen=FRIDAY,
            )
        ],
    )
    s.write(
        "people",
        [
            Person(id="matt-pocock", name="Matt Pocock", status="seed"),
            Person(id="newdev", name="newdev", status="followed"),
        ],
    )
    s.write(
        "jobs",
        [
            JobSnapshot(
                id="global-jobs-hn-2026-11",
                month="2026-11",
                market="global",
                source="jobs-hn",
                total_posts=100,
                keyword_counts={"LLM": 40, "RAG": 25, "MCP": 5},
            )
        ],
    )
    return s


def changes(day=FRIDAY, **kw) -> Changes:
    base = {
        "day": day,
        "new_models": ["opus"],
        "benchmark_moves": [BenchmarkMove(model_id="opus", category="coding", change="entered")],
        "rising": {"repo": ["e1"]},
        "promoted": ["newdev"],
        "people_work": [
            WorkItem(title="Plan then build", url="https://x/w", person_id="matt-pocock")
        ],
    }
    base.update(kw)
    return Changes(**base)


def test_fallback_briefing_lists_changes(store, settings):
    b = build(changes(), store, None, "token expired", settings)
    assert isinstance(b, Briefing) and not b.enriched
    assert "Summaries unavailable today: token expired" in b.markdown
    for expected in (
        "Claude Opus",
        "o/hot",
        "https://github.com/o/hot",
        "Plan then build",
        "newdev",
    ):
        assert expected in b.markdown
    assert settings.site_url in b.markdown


def test_fallback_without_note_still_says_summaries_unavailable(store, settings):
    assert "Summaries unavailable today" in build(changes(), store, None, None, settings).markdown


def test_first_run_headline_counts_everything(store, settings):
    b = build(changes(first_run=True, new_models=[]), store, None, None, settings)
    assert (
        b.headline
        == "Baseline established: Augurai is now tracking 2 models, 1 projects and 2 people."
    )
    assert "new models" not in b.markdown.lower()


def test_enriched_briefing_uses_claude_text(store, settings):
    text = BriefingText(
        headline="Opus takes coding",
        sections=[BriefingSection(title="What changed", body_md="- Opus entered coding")],
        practice_of_the_day="Grill first",
    )
    b = build(changes(), store, text, None, settings)
    assert b.enriched and b.headline == "Opus takes coding"
    assert "## What changed" in b.markdown and "Grill first" in b.markdown
    assert "Summaries unavailable" not in b.markdown


def test_jobs_pulse_only_on_mondays(store, settings):
    assert "Jobs pulse" not in build(changes(FRIDAY), store, None, None, settings).markdown
    monday = build(changes(MONDAY), store, None, None, settings).markdown
    assert "Jobs pulse" in monday and "LLM" in monday


def test_failing_sources_listed_in_footer(store, settings):
    b = build(changes(failing_sources=["jobs-adzuna"]), store, None, None, settings)
    assert "Sources failing 3+ runs: jobs-adzuna" in b.markdown


def test_save_writes_dated_file(tmp_path, store, settings):
    b = build(changes(), store, None, None, settings)
    path = save(b, tmp_path)
    assert path == tmp_path / "briefings" / "2026-11-20.md"
    assert path.read_text(encoding="utf-8").startswith("# ")
