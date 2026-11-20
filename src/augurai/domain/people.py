"""People: seeding, recent work, and autonomous discovery (promotion and dormancy)."""

from datetime import date, timedelta

from augurai.config import Settings
from augurai.models import Entity, Person, RawItem, ScorePoint, WorkItem
from augurai.sources.feeds import linked_logins

WINDOW_DAYS = 30
MAX_WORK_ITEMS = 20
NEW_CANDIDATE_MIN_SIGNAL = 2.0
RISING_OWNER_WEIGHT = 3.0
HN_AUTHOR_WEIGHT = 1.0
LINKED_WEIGHT = 1.0


def _login(person: Person) -> str | None:
    url = person.links.get("github")
    return url.rstrip("/").split("/")[-1].lower() if url else None


def seed(existing: dict[str, Person], settings: Settings) -> dict[str, Person]:
    people = dict(existing)
    for sp in settings.seed_people:
        current = people.get(sp.id)
        if current is None:
            current = Person(id=sp.id, name=sp.name, status="seed")
        people[sp.id] = current.model_copy(
            update={
                "name": sp.name,
                "status": "seed",
                "links": dict(sp.links),
                "why_follow": sp.why_follow,
                "what_to_learn": sp.what_to_learn,
            }
        )
    return people


def attach_work(people: dict[str, Person], items: list[RawItem]) -> dict[str, Person]:
    result = dict(people)
    by_person: dict[str, list[WorkItem]] = {}
    for item in items:
        person_id = item.extra.get("person_id")
        if person_id not in result:
            continue
        by_person.setdefault(person_id, []).append(
            WorkItem(title=item.title, url=item.url, published=item.published, person_id=person_id)
        )
    for person_id, new_work in by_person.items():
        person = result[person_id]
        merged = {w.url: w for w in [*person.recent_work, *new_work]}
        ordered = sorted(
            merged.values(),
            key=lambda w: (w.published is not None, w.published.timestamp() if w.published else 0),
            reverse=True,
        )[:MAX_WORK_ITEMS]
        dates = [w.published.date() for w in ordered if w.published]
        last_active = max(
            [*dates, *([person.last_active] if person.last_active else [])], default=None
        )
        result[person_id] = person.model_copy(
            update={"recent_work": ordered, "last_active": last_active}
        )
    return result


def candidate_signals(
    items: list[RawItem], entities: dict[str, Entity], rising_ids: list[str]
) -> dict[str, float]:
    signals: dict[str, float] = {}

    def add(key: str, weight: float) -> None:
        signals[key] = signals.get(key, 0.0) + weight

    for entity_id in rising_ids:
        entity = entities.get(entity_id)
        if entity and entity.kind != "mcp" and entity.owner_type == "User" and entity.owner:
            add(entity.owner, RISING_OWNER_WEIGHT)
    for item in items:
        if item.kind == "hn":
            # The submitter's HN username is not a GitHub login; the linked repo's owner is.
            for login in linked_logins(str(item.extra.get("linked_url") or "")):
                add(login, HN_AUTHOR_WEIGHT)
        if item.extra.get("person_id"):
            for login in set(item.extra.get("linked_people", [])):
                add(login, LINKED_WEIGHT)
    return signals


def _window_sum(history: list[ScorePoint], day: date) -> float:
    start = day - timedelta(days=WINDOW_DAYS - 1)
    return sum(p.score for p in history if start <= p.day <= day)


def _streak(history: list[ScorePoint], today: date, threshold: float) -> int:
    active_days = {p.day for p in history if p.score > 0}
    streak = 0
    for offset in range(WINDOW_DAYS):
        day = today - timedelta(days=offset)
        if day in active_days and _window_sum(history, day) >= threshold:
            streak += 1
        else:
            break
    return streak


def _resolve(people: dict[str, Person], key: str) -> str | None:
    if key in people:
        return key
    lowered = key.lower()
    for person_id, person in people.items():
        if person_id.lower() == lowered or _login(person) == lowered:
            return person_id
    return None


def update_discovery(
    people: dict[str, Person], signals: dict[str, float], today: date, settings: Settings
) -> tuple[dict[str, Person], list[str], list[str]]:
    result = dict(people)
    todays: dict[str, float] = {}
    for key, signal in signals.items():
        person_id = _resolve(result, key)
        if person_id is None:
            if signal < NEW_CANDIDATE_MIN_SIGNAL:
                continue
            person_id = key
            result[person_id] = Person(
                id=key,
                name=key,
                status="rising",
                links={"github": f"https://github.com/{key}"},
            )
        todays[person_id] = todays.get(person_id, 0.0) + signal

    promoted: list[str] = []
    demoted: list[str] = []
    cutoff = today - timedelta(days=WINDOW_DAYS - 1)
    for person_id, person in list(result.items()):
        history = [p for p in person.score_history if p.day >= cutoff and p.day != today]
        if todays.get(person_id, 0.0) > 0:
            history.append(ScorePoint(day=today, score=todays[person_id]))
        history.sort(key=lambda p: p.day)
        score = _window_sum(history, today)
        streak = _streak(history, today, settings.promote_threshold)
        status = person.status
        last_active = person.last_active

        if (
            status == "dormant"
            and todays.get(person_id, 0.0) > 0
            and score >= settings.promote_threshold
        ):
            status = "rising"
        elif status == "rising" and streak >= settings.promote_consecutive_runs:
            status = "followed"
            promoted.append(person_id)
        elif status == "followed":
            seen = last_active or (history[-1].day if history else None)
            if seen is not None and (today - seen).days > settings.dormant_days:
                status = "dormant"
                demoted.append(person_id)

        if status == "rising" and score == 0 and person.status == "rising":
            del result[person_id]
            continue
        result[person_id] = person.model_copy(
            update={
                "status": status,
                "score": score,
                "score_history": history,
                "above_threshold_runs": streak,
            }
        )
    return result, promoted, demoted
