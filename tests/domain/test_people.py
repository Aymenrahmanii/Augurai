from datetime import UTC, date, datetime, timedelta

from augurai.config import SeedPerson, Settings
from augurai.domain.people import attach_work, candidate_signals, seed, update_discovery
from augurai.models import Entity, Person, RawItem

D1 = date(2026, 11, 18)
D2 = D1 + timedelta(days=1)
S = Settings()


def rising_person(pid: str = "newdev") -> dict[str, Person]:
    return {pid: Person(id=pid, name=pid, status="rising")}


def test_seed_creates_and_refreshes_links():
    settings = Settings(
        seed_people=[
            SeedPerson(
                id="matt-pocock", name="Matt", links={"github": "https://github.com/mattpocock"}
            )
        ]
    )
    people = seed({}, settings)
    assert people["matt-pocock"].status == "seed"
    people["matt-pocock"] = people["matt-pocock"].model_copy(update={"score": 7.0, "links": {}})
    again = seed(people, settings)
    assert again["matt-pocock"].score == 7.0
    assert again["matt-pocock"].links["github"].endswith("mattpocock")


def test_promotion_needs_consecutive_active_days():
    p, promoted, _ = update_discovery(rising_person(), {"newdev": 6.0}, D1, S)
    assert promoted == [] and p["newdev"].above_threshold_runs == 1
    p, promoted, _ = update_discovery(p, {"newdev": 6.0}, D2, S)
    assert promoted == ["newdev"] and p["newdev"].status == "followed"


def test_spike_then_drop_does_not_promote():
    p, _, _ = update_discovery(rising_person(), {"newdev": 6.0}, D1, S)
    p, promoted, _ = update_discovery(p, {}, D2, S)
    assert promoted == []
    assert p["newdev"].status == "rising" and p["newdev"].above_threshold_runs == 0


def test_rerun_same_day_keeps_one_point_and_does_not_double_count():
    p, _, _ = update_discovery(rising_person(), {"newdev": 6.0}, D1, S)
    p, promoted, _ = update_discovery(p, {"newdev": 6.0}, D1, S)
    assert promoted == []
    assert len(p["newdev"].score_history) == 1 and p["newdev"].above_threshold_runs == 1


def test_new_candidate_needs_signal_of_two():
    p, _, _ = update_discovery({}, {"weak": 1.5, "strong": 2.5}, D1, S)
    assert "weak" not in p and p["strong"].status == "rising"
    assert p["strong"].links["github"] == "https://github.com/strong"


def test_signal_for_known_github_login_goes_to_that_person():
    people = {
        "matt-pocock": Person(
            id="matt-pocock",
            name="Matt",
            status="seed",
            links={"github": "https://github.com/mattpocock"},
        )
    }
    p, _, _ = update_discovery(people, {"mattpocock": 3.0}, D1, S)
    assert "mattpocock" not in p and p["matt-pocock"].score == 3.0


def test_seed_never_demoted():
    people = {
        "matt-pocock": Person(
            id="matt-pocock", name="Matt", status="seed", last_active=D1 - timedelta(days=400)
        )
    }
    p, _, demoted = update_discovery(people, {}, D1, S)
    assert demoted == [] and p["matt-pocock"].status == "seed"


def test_followed_goes_dormant_after_ninety_days():
    people = {
        "old": Person(id="old", name="old", status="followed", last_active=D1 - timedelta(days=91))
    }
    p, _, demoted = update_discovery(people, {}, D1, S)
    assert demoted == ["old"] and p["old"].status == "dormant"


def test_dormant_returns_to_rising_when_active_again():
    people = {"old": Person(id="old", name="old", status="dormant")}
    p, _, _ = update_discovery(people, {"old": 6.0}, D1, S)
    assert p["old"].status == "rising"


def test_stale_rising_person_is_pruned():
    from augurai.models import ScorePoint

    people = {
        "gone": Person(
            id="gone",
            name="gone",
            status="rising",
            score_history=[ScorePoint(day=D1 - timedelta(days=40), score=2.0)],
        )
    }
    p, _, _ = update_discovery(people, {}, D1, S)
    assert "gone" not in p


def test_attach_work_dedupes_and_caps_and_sets_last_active():
    people = {"a": Person(id="a", name="A", status="seed")}
    items = [
        RawItem(
            id=str(n),
            source="feeds",
            kind="post",
            title=f"t{n % 25}",
            url=f"https://x/{n % 25}",
            published=datetime(2026, 11, 1, tzinfo=UTC) + timedelta(days=n % 25),
            extra={"person_id": "a"},
        )
        for n in range(50)
    ]
    out = attach_work(people, items)
    assert len(out["a"].recent_work) == 20
    assert len({w.url for w in out["a"].recent_work}) == 20
    assert out["a"].last_active == date(2026, 11, 25)


def test_attach_work_ignores_unknown_people():
    item = RawItem(
        id="1", source="s", kind="post", title="t", url="https://x", extra={"person_id": "ghost"}
    )
    assert attach_work({}, [item]) == {}


def test_candidate_signals_weights():
    entities = {
        "e1": Entity(id="e1", kind="repo", name="n", url="u", owner="alice", first_seen=D1),
        "e2": Entity(
            id="e2",
            kind="repo",
            name="n",
            url="u",
            owner="acme",
            first_seen=D1,
            owner_type="Organization",
        ),
        "e3": Entity(id="e3", kind="mcp", name="n", url="u", owner="io.github.bob", first_seen=D1),
    }
    items = [
        RawItem(
            id="h",
            source="hackernews",
            kind="hn",
            title="t",
            url="u",
            author="submitter",
            extra={"linked_url": "https://github.com/carol/proj"},
        ),
        RawItem(
            id="h2",
            source="hackernews",
            kind="hn",
            title="t",
            url="u9",
            author="other",
            extra={"linked_url": "https://example.com/post"},
        ),
        RawItem(
            id="p",
            source="feeds",
            kind="post",
            title="t",
            url="u2",
            extra={"person_id": "x", "linked_people": ["dave", "dave"]},
        ),
        RawItem(
            id="q",
            source="feeds",
            kind="post",
            title="t",
            url="u3",
            extra={"linked_people": ["erin"]},
        ),
    ]
    signals = candidate_signals(items, entities, ["e1", "e2", "e3"])
    assert signals == {"alice": 3.0, "carol": 1.0, "dave": 1.0}
