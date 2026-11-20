import json
from datetime import UTC, datetime

import httpx

from augurai.models import RawItem
from augurai.pipeline import collect
from augurai.sources.base import SourceError

NOW = datetime(2026, 11, 20, 5, 0, tzinfo=UTC)


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
                extra={
                    "model_key": "opus",
                    "provider": "anthropic",
                    "price_in": 5.0,
                    "price_out": 25.0,
                },
            )
        ]


class FakeRepos:
    name = "fake-repos"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return [
            RawItem(
                id="r",
                source="github-repos",
                kind="repo",
                title="o/r",
                url="https://github.com/o/r",
                metrics={"stars": 10},
                extra={"owner": "o", "description": "d"},
            )
        ]


class FakeFeed:
    name = "fake-feed"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return [
            RawItem(
                id="f",
                source="feeds",
                kind="post",
                title="A post",
                url="https://x/post",
                extra={"person_id": "matt-pocock"},
            )
        ]


class Boom:
    name = "boom"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        raise SourceError("down")


def run_collect(root, settings, sources, mode="refresh"):
    return collect(root, settings, mode, NOW, sources=sources, env={}, http=httpx.Client())


def test_collect_end_to_end_with_fake_sources(tmp_path, settings):
    changes = run_collect(tmp_path, settings, [FakeModels(), FakeRepos(), FakeFeed()])
    assert changes.first_run is True
    for name in ("models", "entities", "people", "health"):
        assert (tmp_path / "data" / f"{name}.json").exists()
    assert (tmp_path / "work" / "changes.json").exists()
    people = json.loads((tmp_path / "data" / "people.json").read_text(encoding="utf-8"))
    matt = next(p for p in people if p["id"] == "matt-pocock")
    assert matt["recent_work"][0]["url"] == "https://x/post"
    seeds = [p for p in people if p["status"] == "seed"]
    assert len(seeds) == 16  # seed people exist even when no source mentions them
    owner = next(p for p in people if p["id"] == "o")  # owner of a rising repo becomes a candidate
    assert owner["status"] == "rising"


def test_second_run_detects_new_model(tmp_path, settings):
    run_collect(tmp_path, settings, [FakeModels()])

    class MoreModels(FakeModels):
        def fetch(self, ctx):
            extra = (
                super()
                .fetch(ctx)[0]
                .model_copy(
                    update={
                        "id": "m2",
                        "url": "https://x/sonnet",
                        "extra": {"model_key": "sonnet", "provider": "anthropic"},
                    }
                )
            )
            return [*super().fetch(ctx), extra]

    changes = run_collect(tmp_path, settings, [MoreModels()])
    assert changes.first_run is False and changes.new_models == ["sonnet"]


def test_collect_keeps_data_when_all_sources_fail(tmp_path, settings):
    run_collect(tmp_path, settings, [FakeModels()])
    path = tmp_path / "data" / "models.json"
    before = path.read_text(encoding="utf-8")
    run_collect(tmp_path, settings, [Boom()])
    assert path.read_text(encoding="utf-8") == before
    health = json.loads((tmp_path / "data" / "health.json").read_text(encoding="utf-8"))
    assert {h["id"]: h["consecutive_failures"] for h in health}["boom"] == 1
