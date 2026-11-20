from datetime import date, timedelta

import pytest

from augurai.domain.ecosystem import merge_entities, rising, velocity_7d
from augurai.models import Entity, RawItem, StarSnapshot

TODAY = date(2026, 11, 20)


def repo_item(name: str, stars: int, kind: str = "repo") -> RawItem:
    return RawItem(
        id=name,
        source="github-repos",
        kind=kind,
        title=name,
        url=f"https://github.com/o/{name}",
        metrics={"stars": float(stars)},
        extra={"owner": "o", "description": "d"},
    )


def entity(eid: str, velocity: float, first_seen: date, seen: date | None = None) -> Entity:
    return Entity(
        id=eid,
        kind="repo",
        name=eid,
        url="u",
        owner="o",
        velocity_7d=velocity,
        first_seen=first_seen,
        star_snapshots=[StarSnapshot(day=seen or TODAY, stars=0)],
    )


def test_velocity_needs_two_snapshots():
    assert velocity_7d([StarSnapshot(day=TODAY, stars=10)], TODAY) == 0.0


def test_velocity_per_day():
    snaps = [
        StarSnapshot(day=TODAY - timedelta(days=7), stars=100),
        StarSnapshot(day=TODAY, stars=170),
    ]
    assert velocity_7d(snaps, TODAY) == pytest.approx(10.0)


def test_velocity_uses_snapshot_closest_to_seven_days_ago():
    snaps = [
        StarSnapshot(day=TODAY - timedelta(days=30), stars=0),
        StarSnapshot(day=TODAY - timedelta(days=6), stars=100),
        StarSnapshot(day=TODAY, stars=160),
    ]
    assert velocity_7d(snaps, TODAY) == pytest.approx(10.0)


def test_one_snapshot_per_day():
    e = merge_entities({}, [repo_item("a", 5)], TODAY)
    e = merge_entities(e, [repo_item("a", 9)], TODAY)
    assert [s.stars for s in e["a"].star_snapshots] == [9]
    assert e["a"].stars == 9


def test_snapshots_capped_at_sixty():
    entities: dict[str, Entity] = {}
    for offset in range(70):
        entities = merge_entities(
            entities, [repo_item("a", offset)], TODAY + timedelta(days=offset)
        )
    assert len(entities["a"].star_snapshots) == 60


def test_merge_keeps_entities_missing_from_new_items():
    e = merge_entities({}, [repo_item("a", 5)], TODAY)
    e = merge_entities(e, [repo_item("b", 5)], TODAY + timedelta(days=1))
    assert set(e) == {"a", "b"}


def test_higher_priority_kind_wins():
    e = merge_entities({}, [repo_item("a", 5, "repo")], TODAY)
    e = merge_entities(e, [repo_item("a", 5, "skill")], TODAY)
    assert e["a"].kind == "skill"


def test_rising_orders_by_velocity_with_novelty():
    entities = {
        "old": entity("old", 10.0, TODAY - timedelta(days=100)),
        "new": entity("new", 10.0, TODAY - timedelta(days=2)),
        "slow": entity("slow", 1.0, TODAY - timedelta(days=100)),
    }
    assert rising(entities, "repo", 2, TODAY) == ["new", "old"]


def test_rising_without_velocity_prefers_newest():
    entities = {
        "a": entity("a", 0.0, TODAY - timedelta(days=50)),
        "b": entity("b", 0.0, TODAY - timedelta(days=1)),
    }
    assert rising(entities, "repo", 1, TODAY) == ["b"]


def test_stale_entities_are_not_rising():
    entities = {
        "fresh": entity("fresh", 1.0, TODAY - timedelta(days=100)),
        "stale": entity("stale", 99.0, TODAY - timedelta(days=100), seen=TODAY - timedelta(days=5)),
    }
    assert rising(entities, "repo", 5, TODAY) == ["fresh"]
