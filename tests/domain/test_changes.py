from datetime import date

from augurai.domain.changes import Changes, Snapshot, compute
from augurai.models import Model, Person, RawItem, SourceHealth, WorkItem
from augurai.sources.base import SourceRun

TODAY = date(2026, 11, 20)


def model(mid: str, best_at=()) -> Model:
    return Model(id=mid, name=mid, provider="p", first_seen=TODAY, best_at=list(best_at))


def empty_run() -> SourceRun:
    return SourceRun()


def test_first_run_flag_and_no_flood():
    many = {f"m{i}": model(f"m{i}") for i in range(50)}
    changes = compute(Snapshot({}, {}, {}), Snapshot(many, {}, {}), empty_run(), TODAY)
    assert changes.first_run is True
    assert changes.new_models == [] and changes.benchmark_moves == []


def test_new_model_detected():
    before = Snapshot({"a": model("a")}, {}, {})
    after = Snapshot({"a": model("a"), "b": model("b")}, {}, {})
    assert compute(before, after, empty_run(), TODAY).new_models == ["b"]


def test_benchmark_move_entered_and_left():
    before = Snapshot({"a": model("a", ["coding"]), "b": model("b")}, {}, {})
    after = Snapshot({"a": model("a"), "b": model("b", ["coding"])}, {}, {})
    moves = {
        (m.model_id, m.category, m.change)
        for m in compute(before, after, empty_run(), TODAY).benchmark_moves
    }
    assert moves == {("b", "coding", "entered"), ("a", "coding", "left")}


def test_people_work_is_only_new_items():
    old = WorkItem(title="old", url="https://x/old", person_id="p")
    new = WorkItem(title="new", url="https://x/new", person_id="p")
    mk = lambda work: {"p": Person(id="p", name="P", status="seed", recent_work=work)}
    before = Snapshot({"a": model("a")}, {}, mk([old]))
    after = Snapshot({"a": model("a")}, {}, mk([new, old]))
    assert [w.url for w in compute(before, after, empty_run(), TODAY).people_work] == [
        "https://x/new"
    ]


def test_top_hn_and_papers_ordered_by_metric_and_failing_sources():
    run = SourceRun(
        items=[
            RawItem(
                id="h1",
                source="hackernews",
                kind="hn",
                title="a",
                url="u1",
                metrics={"points": 100},
            ),
            RawItem(
                id="h2",
                source="hackernews",
                kind="hn",
                title="b",
                url="u2",
                metrics={"points": 300},
            ),
            RawItem(
                id="p1",
                source="hf-papers",
                kind="paper",
                title="c",
                url="u3",
                metrics={"upvotes": 9},
            ),
        ],
        health={
            "bad": SourceHealth(id="bad", consecutive_failures=3),
            "meh": SourceHealth(id="meh", consecutive_failures=2),
        },
    )
    changes = compute(
        Snapshot({"a": model("a")}, {}, {}), Snapshot({"a": model("a")}, {}, {}), run, TODAY
    )
    assert changes.top_hn == ["h2", "h1"] and changes.top_papers == ["p1"]
    assert changes.failing_sources == ["bad"]


def test_passes_through_rising_and_promotions():
    snap = Snapshot({"a": model("a")}, {}, {})
    changes = compute(
        snap, snap, empty_run(), TODAY, rising={"repo": ["x"]}, promoted=["newdev"], demoted=[]
    )
    assert changes.rising == {"repo": ["x"]} and changes.promoted == ["newdev"]
    assert isinstance(changes, Changes)
