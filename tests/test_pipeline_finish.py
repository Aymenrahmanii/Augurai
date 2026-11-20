import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from augurai.models import RawItem, RunRecord
from augurai.pipeline import collect, finish
from augurai.store import Store

NOW = datetime(2026, 11, 20, 4, 30, tzinfo=UTC)


class FakeModels:
    name = "fake-models"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return [
            RawItem(
                id="m",
                source="openrouter",
                kind="model",
                title="Opus",
                url="https://x/opus",
                extra={"model_key": "opus", "provider": "anthropic"},
            )
        ]


class FakeExtra:
    name = "fake-extra"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return [
            RawItem(
                id="e",
                source="openrouter",
                kind="model",
                title="Extra",
                url="https://x/extra",
                extra={"model_key": "extra", "provider": "p"},
            )
        ]


@pytest.fixture
def collected_root(tmp_path, settings):
    collect(tmp_path, settings, "morning", NOW, sources=[FakeModels()], env={}, http=httpx.Client())
    return tmp_path


def write_output(root, headline="Claude wrote this"):
    payload = {
        "briefing": {
            "headline": headline,
            "sections": [{"title": "What changed", "body_md": "- Opus"}],
            "practice_of_the_day": "Grill first",
        }
    }
    (root / "work" / "enrich_output.json").write_text(json.dumps(payload), encoding="utf-8")


def runs(root):
    return Store(root / "data").read("runs", RunRecord)


def briefing_text(root, day="2026-11-20") -> str:
    return (root / "briefings" / f"{day}.md").read_text(encoding="utf-8")


def pending(root):
    return json.loads((root / "data" / "pending_changes.json").read_text(encoding="utf-8"))


def collect_extra(root, settings):
    return collect(
        root,
        settings,
        "morning",
        NOW + timedelta(minutes=5),
        sources=[FakeModels(), FakeExtra()],
        env={},
        http=httpx.Client(),
    )


def test_morning_without_claude_output_falls_back(collected_root, settings):
    record = finish(collected_root, settings, "morning", NOW)
    assert record.enrichment == "failed" and record.briefing_written
    assert "Claude step did not produce output" in record.enrichment_note
    assert "Summaries unavailable today" in briefing_text(collected_root)


def test_morning_with_valid_output_uses_claude_text(collected_root, settings):
    write_output(collected_root)
    record = finish(collected_root, settings, "morning", NOW)
    assert record.enrichment == "ran" and record.briefing_written
    assert "Claude wrote this" in briefing_text(collected_root)


def test_a_later_morning_run_never_overwrites_the_days_briefing(collected_root, settings):
    write_output(collected_root)
    first = finish(collected_root, settings, "morning", NOW)
    (collected_root / "work" / "enrich_output.json").unlink()
    second = finish(collected_root, settings, "morning", NOW + timedelta(minutes=40))
    assert first.briefing_written is True and second.briefing_written is False
    assert "Claude wrote this" in briefing_text(collected_root)


def test_pending_changes_cleared_once_the_briefing_is_written(collected_root, settings):
    changes = collect_extra(collected_root, settings)
    assert changes.new_models == ["extra"] and pending(collected_root)["new_models"] == ["extra"]
    finish(collected_root, settings, "morning", NOW + timedelta(minutes=10))
    assert pending(collected_root)["new_models"] == []
    assert "Extra" in briefing_text(collected_root)


def test_next_day_briefing_is_written_even_if_yesterdays_exists(collected_root, settings):
    finish(collected_root, settings, "morning", NOW)
    tomorrow = NOW + timedelta(days=1)
    collect(
        collected_root,
        settings,
        "morning",
        tomorrow,
        sources=[FakeModels()],
        env={},
        http=httpx.Client(),
    )
    record = finish(collected_root, settings, "morning", tomorrow)
    assert record.briefing_written is True
    assert (collected_root / "briefings" / "2026-11-21.md").exists()


def test_refresh_writes_no_briefing_and_skips_enrichment(tmp_path, settings):
    collect(tmp_path, settings, "refresh", NOW, sources=[FakeModels()], env={}, http=httpx.Client())
    record = finish(tmp_path, settings, "refresh", NOW)
    assert record.enrichment == "skipped" and record.briefing_written is False
    assert not (tmp_path / "briefings").exists()
    assert (tmp_path / "_site" / "index.html").exists()


def test_record_carries_source_results(collected_root, settings):
    record = finish(collected_root, settings, "morning", NOW)
    assert record.sources_ok == ["fake-models"] and record.mode == "morning"


def test_finish_without_changes_file_still_builds_site(tmp_path, settings):
    record = finish(tmp_path, settings, "refresh", NOW)
    assert (tmp_path / "_site" / "index.html").exists()
    assert record.enrichment == "skipped"


def test_runs_are_capped_at_two_hundred(tmp_path, settings, monkeypatch):
    monkeypatch.setattr("augurai.pipeline.build_site", lambda *args, **kwargs: [])
    for n in range(205):
        finish(tmp_path, settings, "refresh", NOW + timedelta(minutes=n))
    assert len(runs(tmp_path)) == 200
