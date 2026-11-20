from augurai.models import RawItem, SourceHealth
from augurai.sources.base import SourceError, run_sources


def item(n: str) -> RawItem:
    return RawItem(id=n, source="t", kind="post", title=n, url=f"https://x/{n}")


class Boom:
    name = "boom"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        raise SourceError("kaput")


class Ok:
    name = "ok"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return [item("a")]


class Empty:
    name = "empty"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx):
        return []


class NeedsKey:
    name = "needs-key"
    required_env = ("SOME_KEY",)

    def fetch(self, ctx):
        raise AssertionError("must not run without env")


def test_failure_is_isolated_and_counted(ctx):
    run = run_sources([Boom(), Ok()], ctx, {})
    assert run.failed == ["boom"] and run.ok == ["ok"]
    assert run.health["boom"].consecutive_failures == 1
    assert len(run.items) == 1


def test_empty_result_counts_as_failure(ctx):
    run = run_sources([Empty()], ctx, {})
    assert run.failed == ["empty"]


def test_missing_env_is_skipped(ctx):
    run = run_sources([NeedsKey()], ctx, {})
    assert run.skipped == ["needs-key"]
    assert run.health["needs-key"].consecutive_failures == 0
    assert run.health["needs-key"].last_error == "missing env: SOME_KEY"


def test_success_resets_failures(ctx):
    health = {"ok": SourceHealth(id="ok", consecutive_failures=4)}
    run = run_sources([Ok()], ctx, health)
    assert run.health["ok"].consecutive_failures == 0
    assert run.health["ok"].last_success == ctx.now


def test_unexpected_exception_does_not_propagate(ctx):
    class Weird(Boom):
        name = "weird"

        def fetch(self, ctx):
            raise ZeroDivisionError("x" * 500)

    run = run_sources([Weird()], ctx, {})
    assert run.failed == ["weird"]
    assert len(run.health["weird"].last_error) <= 300
