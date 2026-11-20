"""Source protocol and the runner that isolates each source's failures."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx

from augurai.config import Settings
from augurai.models import RawItem, SourceHealth


class SourceError(Exception):
    pass


@dataclass
class SourceContext:
    settings: Settings
    http: httpx.Client
    now: datetime
    env: Mapping[str, str]


class Source(Protocol):
    name: str
    required_env: tuple[str, ...]

    def fetch(self, ctx: SourceContext) -> list[RawItem]: ...


@dataclass
class SourceRun:
    items: list[RawItem] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    health: dict[str, SourceHealth] = field(default_factory=dict)


def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=20.0,
        transport=httpx.HTTPTransport(retries=3),
        headers={"User-Agent": "augurai/0.1"},
        follow_redirects=True,
    )


def github_headers(env: Mapping[str, str]) -> dict[str, str]:
    """Auth + API headers for api.github.com requests; token is optional."""
    headers = {"Accept": "application/vnd.github+json"}
    if token := env.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def run_sources(
    sources: Sequence[Source], ctx: SourceContext, health: dict[str, SourceHealth]
) -> SourceRun:
    run = SourceRun(health=dict(health))
    for source in sources:
        record = run.health.get(source.name) or SourceHealth(id=source.name)
        missing = [name for name in source.required_env if not ctx.env.get(name)]
        if missing:
            record = record.model_copy(update={"last_error": f"missing env: {', '.join(missing)}"})
            run.skipped.append(source.name)
        else:
            try:
                items = source.fetch(ctx)
                if not items:
                    raise SourceError("empty result")
            except Exception as exc:  # noqa: BLE001 - one source must never fail the run
                message = f"{type(exc).__name__}: {exc}"[:300]
                record = record.model_copy(
                    update={
                        "last_error": message,
                        "consecutive_failures": record.consecutive_failures + 1,
                    }
                )
                run.failed.append(source.name)
            else:
                record = record.model_copy(
                    update={
                        "last_success": ctx.now,
                        "last_error": None,
                        "consecutive_failures": 0,
                    }
                )
                run.items.extend(items)
                run.ok.append(source.name)
        run.health[source.name] = record
    return run
