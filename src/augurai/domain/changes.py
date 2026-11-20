"""What changed between two runs: the input to the briefing."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from augurai.models import Category, Entity, Model, Person, WorkItem
from augurai.sources.base import SourceRun

TOP_N = 10
FAILING_AFTER = 3


class BenchmarkMove(BaseModel):
    model_id: str
    category: Category
    change: Literal["entered", "left"]


class Changes(BaseModel):
    day: date
    first_run: bool = False
    new_models: list[str] = Field(default_factory=list)
    benchmark_moves: list[BenchmarkMove] = Field(default_factory=list)
    rising: dict[str, list[str]] = Field(default_factory=dict)
    promoted: list[str] = Field(default_factory=list)
    demoted: list[str] = Field(default_factory=list)
    people_work: list[WorkItem] = Field(default_factory=list)
    top_hn: list[str] = Field(default_factory=list)
    top_papers: list[str] = Field(default_factory=list)
    failing_sources: list[str] = Field(default_factory=list)


@dataclass
class Snapshot:
    models: dict[str, Model]
    entities: dict[str, Entity]
    people: dict[str, Person]


def _benchmark_moves(before: dict[str, Model], after: dict[str, Model]) -> list[BenchmarkMove]:
    moves: list[BenchmarkMove] = []
    for model_id in sorted(after):
        old = set(before[model_id].best_at) if model_id in before else set()
        new = set(after[model_id].best_at)
        moves += [
            BenchmarkMove(model_id=model_id, category=c, change="entered")
            for c in sorted(new - old)
        ]
        moves += [
            BenchmarkMove(model_id=model_id, category=c, change="left") for c in sorted(old - new)
        ]
    return moves


def _new_work(before: dict[str, Person], after: dict[str, Person]) -> list[WorkItem]:
    seen = {w.url for p in before.values() for w in p.recent_work}
    fresh = [w for p in after.values() for w in p.recent_work if w.url not in seen]
    return sorted(
        fresh, key=lambda w: (w.published is None, -(w.published.timestamp() if w.published else 0))
    )


def _top(run: SourceRun, kind: str, metric: str) -> list[str]:
    items = [i for i in run.items if i.kind == kind]
    items.sort(key=lambda i: (-i.metrics.get(metric, 0.0), i.id))
    return [i.id for i in items[:TOP_N]]


def compute(
    before: Snapshot,
    after: Snapshot,
    run: SourceRun,
    today: date,
    rising: dict[str, list[str]] | None = None,
    promoted: list[str] | None = None,
    demoted: list[str] | None = None,
) -> Changes:
    first_run = not before.models and not before.entities
    return Changes(
        day=today,
        first_run=first_run,
        new_models=[] if first_run else sorted(set(after.models) - set(before.models)),
        benchmark_moves=[] if first_run else _benchmark_moves(before.models, after.models),
        rising=rising or {},
        promoted=promoted or [],
        demoted=demoted or [],
        people_work=[] if first_run else _new_work(before.people, after.people),
        top_hn=_top(run, "hn", "points"),
        top_papers=_top(run, "paper", "upvotes"),
        failing_sources=sorted(
            name for name, h in run.health.items() if h.consecutive_failures >= FAILING_AFTER
        ),
    )
