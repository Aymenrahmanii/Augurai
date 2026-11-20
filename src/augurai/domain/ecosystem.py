"""Track repos, skills, agents and MCP servers: star snapshots, velocity and rising lists."""

from datetime import date

from augurai.models import Entity, EntityKind, RawItem, StarSnapshot

MAX_SNAPSHOTS = 60
NOVELTY_DAYS = 14
NOVELTY_BONUS = 1.2
_KIND_PRIORITY: dict[str, int] = {"repo": 0, "agent": 1, "mcp": 2, "skill": 3}


def velocity_7d(snapshots: list[StarSnapshot], today: date) -> float:
    """Stars gained per day, measured against the snapshot closest to seven days ago."""
    if len(snapshots) < 2:
        return 0.0
    latest = max(snapshots, key=lambda s: s.day)
    older = [s for s in snapshots if s.day < latest.day]
    if not older:
        return 0.0
    baseline = min(older, key=lambda s: abs((latest.day - s.day).days - 7))
    days = (latest.day - baseline.day).days
    return (latest.stars - baseline.stars) / days if days else 0.0


def _upsert(existing: Entity | None, item: RawItem, today: date) -> Entity:
    stars = int(item.metrics.get("stars", 0))
    entity = existing or Entity(
        id=item.id,
        kind=item.kind,  # type: ignore[arg-type]
        name=item.title,
        url=item.url,
        owner=str(item.extra.get("owner", "")),
        first_seen=today,
    )
    kind: EntityKind = entity.kind
    if _KIND_PRIORITY.get(item.kind, 0) > _KIND_PRIORITY.get(kind, 0):
        kind = item.kind  # type: ignore[assignment]
    snapshots = [s for s in entity.star_snapshots if s.day != today]
    snapshots.append(StarSnapshot(day=today, stars=stars))
    snapshots = sorted(snapshots, key=lambda s: s.day)[-MAX_SNAPSHOTS:]
    return entity.model_copy(
        update={
            "kind": kind,
            "name": item.title,
            "description": str(item.extra.get("description", entity.description)),
            "stars": stars,
            "star_snapshots": snapshots,
            "velocity_7d": velocity_7d(snapshots, today),
        }
    )


def merge_entities(
    existing: dict[str, Entity], items: list[RawItem], today: date
) -> dict[str, Entity]:
    merged = dict(existing)
    for item in items:
        merged[item.id] = _upsert(merged.get(item.id), item, today)
    return merged


def rising(entities: dict[str, Entity], kind: str, top_n: int, today: date) -> list[str]:
    def key(entity: Entity) -> tuple[float, int, str]:
        is_new = (today - entity.first_seen).days <= NOVELTY_DAYS
        score = entity.velocity_7d * (NOVELTY_BONUS if is_new else 1.0)
        return (-score, -entity.first_seen.toordinal(), entity.id)

    candidates = sorted((e for e in entities.values() if e.kind == kind), key=key)
    return [e.id for e in candidates[:top_n]]
