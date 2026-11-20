import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from augurai import mailer
from augurai.models import RawItem, RunRecord
from augurai.pipeline import collect, finish
from augurai.store import Store

NOW = datetime(2026, 11, 20, 4, 30, tzinfo=UTC)
ENV = {"GMAIL_USER": "me@example.com", "GMAIL_APP_PASSWORD": "pw", "BRIEFING_TO": "to@example.com"}


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


class FakeSend:
    def __init__(self) -> None:
        self.messages: list = []
        self.results: list[bool] = []

    def __call__(self, msg, env) -> bool:
        self.messages.append(msg)
        return self.results.pop(0) if self.results else True


@pytest.fixture
def fake_send(monkeypatch):
    sender = FakeSend()
    monkeypatch.setattr(mailer, "send", sender)
    return sender


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


def test_morning_twice_sends_once(collected_root, settings, fake_send):
    finish(collected_root, settings, "morning", NOW, ENV)
    finish(collected_root, settings, "morning", NOW + timedelta(minutes=40), ENV)
    assert len(fake_send.messages) == 1
    assert [r.email_sent for r in runs(collected_root)] == [True, False]


def test_morning_without_claude_output_falls_back(collected_root, settings, fake_send):
    record = finish(collected_root, settings, "morning", NOW, ENV)
    assert record.enrichment == "failed" and record.email_sent
    assert "Claude step did not produce output" in record.enrichment_note
    briefing = (collected_root / "briefings" / "2026-11-20.md").read_text(encoding="utf-8")
    assert "Summaries unavailable today" in briefing


def test_morning_with_valid_output_uses_claude_text(collected_root, settings, fake_send):
    write_output(collected_root)
    record = finish(collected_root, settings, "morning", NOW, ENV)
    assert record.enrichment == "ran"
    assert "Claude wrote this" in fake_send.messages[0]["Subject"]
    assert "Claude wrote this" in (collected_root / "briefings" / "2026-11-20.md").read_text(
        encoding="utf-8"
    )


def test_failed_email_is_retried_by_the_next_morning_run(collected_root, settings, fake_send):
    fake_send.results = [False, True]
    first = finish(collected_root, settings, "morning", NOW, ENV)
    second = finish(collected_root, settings, "morning", NOW + timedelta(minutes=40), ENV)
    assert first.email_sent is False and second.email_sent is True
    assert len(fake_send.messages) == 2


def test_refresh_never_emails_and_skips_enrichment(tmp_path, settings, fake_send):
    collect(tmp_path, settings, "refresh", NOW, sources=[FakeModels()], env={}, http=httpx.Client())
    record = finish(tmp_path, settings, "refresh", NOW, ENV)
    assert record.enrichment == "skipped" and record.email_sent is False
    assert fake_send.messages == []
    assert not (tmp_path / "briefings").exists()
    assert (tmp_path / "_site" / "index.html").exists()


def test_record_carries_source_results(collected_root, settings, fake_send):
    record = finish(collected_root, settings, "morning", NOW, ENV)
    assert record.sources_ok == ["fake-models"] and record.mode == "morning"


def test_finish_without_changes_file_still_builds_site(tmp_path, settings, fake_send):
    record = finish(tmp_path, settings, "refresh", NOW, ENV)
    assert (tmp_path / "_site" / "index.html").exists()
    assert record.enrichment == "skipped"


def test_runs_are_capped_at_two_hundred(tmp_path, settings, fake_send, monkeypatch):
    monkeypatch.setattr("augurai.pipeline.build_site", lambda *args, **kwargs: [])
    for n in range(205):
        finish(tmp_path, settings, "refresh", NOW + timedelta(minutes=n), ENV)
    assert len(runs(tmp_path)) == 200


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


def test_pending_changes_cleared_after_the_briefing_is_sent(collected_root, settings, fake_send):
    changes = collect_extra(collected_root, settings)
    assert changes.new_models == ["extra"] and pending(collected_root)["new_models"] == ["extra"]
    finish(collected_root, settings, "morning", NOW + timedelta(minutes=10), ENV)
    assert pending(collected_root)["new_models"] == []


def test_pending_changes_kept_when_the_email_fails(collected_root, settings, fake_send):
    collect_extra(collected_root, settings)
    fake_send.results = [False]
    record = finish(collected_root, settings, "morning", NOW + timedelta(minutes=10), ENV)
    assert record.email_failed is True and record.email_sent is False
    assert pending(collected_root)["new_models"] == ["extra"]


def test_a_second_run_that_skips_the_email_is_not_a_failure(collected_root, settings, fake_send):
    finish(collected_root, settings, "morning", NOW, ENV)
    second = finish(collected_root, settings, "morning", NOW + timedelta(minutes=40), ENV)
    assert second.email_failed is False
