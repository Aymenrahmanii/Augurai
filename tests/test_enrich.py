import json
from datetime import date

import pytest

from augurai.domain.changes import Changes
from augurai.enrich import EnrichInput, EnrichItem, merge, prepare
from augurai.models import Entity, Model, Person, Practice, RawItem, Summary, WorkItem
from augurai.store import Store

TODAY = date(2026, 11, 20)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "data")
    s.write("people", [Person(id="matt-pocock", name="Matt", status="seed")])
    s.write(
        "models",
        [Model(id="opus", name="Opus", provider="anthropic", first_seen=TODAY)],
    )
    s.write(
        "practices",
        [
            Practice(
                id="plan-first",
                title="Plan first",
                principle="p",
                how_to_apply="h",
                person_id="matt-pocock",
                source_url="https://x/old",
                first_seen=TODAY,
            )
        ],
    )
    s.write(
        "entities",
        [Entity(id="i1", kind="repo", name="o/r", url="https://x/r", owner="o", first_seen=TODAY)],
    )
    return s


@pytest.fixture
def inp():
    return EnrichInput(
        day=TODAY,
        items=[
            EnrichItem(id="i1", kind="repo", title="o/r", url="https://x/r", text="a repo"),
            EnrichItem(id="i2", kind="post", title="A post", url="https://x/post", text="a post"),
        ],
        new_people_work=[
            WorkItem(title="A post", url="https://x/post", person_id="matt-pocock"),
            WorkItem(title="Another", url="https://x/new", person_id="matt-pocock"),
        ],
        models=[],
        existing_practices=[],
        changes=Changes(day=TODAY),
    )


def test_missing_output_is_skipped(tmp_path, store, inp):
    assert merge(store, tmp_path / "nope.json", inp, TODAY)[0] == "skipped"


def test_garbage_is_failed(store, inp, fixture_path):
    status, note, briefing = merge(store, fixture_path("enrich/garbage.json"), inp, TODAY)
    assert status == "failed" and briefing is None and note


def test_valid_output_is_merged(store, inp, fixture_path):
    status, note, briefing = merge(store, fixture_path("enrich/valid.json"), inp, TODAY)
    assert status == "ran" and note is None
    assert briefing is not None and briefing.headline == "H"
    assert [s.text for s in store.read("summaries", Summary)] == ["Short summary."]
    assert store.read_map("entities", Entity)["i1"].summary == "Short summary."
    practices = store.read_map("practices", Practice)
    assert "plan-first" in practices and len(practices) == 2
    assert store.read_map("models", Model)["opus"].use_cases == ["coding"]


def test_partial_keeps_valid_parts(store, inp, fixture_path):
    status, note, briefing = merge(store, fixture_path("enrich/partial.json"), inp, TODAY)
    assert status == "partial" and "dropped" in note
    assert briefing is not None
    people = {p.id for p in store.read("people", Person)}
    assert all(p.person_id in people for p in store.read("practices", Practice))
    assert [s.id for s in store.read("summaries", Summary)] == ["i1"]
    assert store.read_map("models", Model)["opus"].avoid_for == ["bulk work"]


def test_reinforcing_an_existing_practice_adds_source(store, inp, tmp_path):
    out = tmp_path / "out.json"
    out.write_text(
        json.dumps(
            {
                "practices": [
                    {
                        "title": "Plan first again",
                        "principle": "p",
                        "how_to_apply": "h",
                        "person_id": "matt-pocock",
                        "source_url": "https://x/new",
                        "reinforces": "plan-first",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert merge(store, out, inp, TODAY)[0] == "ran"
    practices = store.read_map("practices", Practice)
    assert len(practices) == 1 and practices["plan-first"].reinforced_by == ["https://x/new"]


def test_long_text_is_capped(store, inp, tmp_path):
    out = tmp_path / "out.json"
    out.write_text(
        json.dumps(
            {
                "summaries": {"i1": "x" * 900},
                "briefing": {
                    "headline": "H",
                    "sections": [{"title": "t", "body_md": "y" * 5000}],
                    "practice_of_the_day": "z",
                },
            }
        ),
        encoding="utf-8",
    )
    _, _, briefing = merge(store, out, inp, TODAY)
    assert len(store.read("summaries", Summary)[0].text) == 300
    assert len(briefing.sections[0].body_md) == 1200


def test_prepare_caps_and_skips_cached(store, settings, tmp_path):
    store.write("summaries", [Summary(id="r0", text="cached")])
    items = [
        RawItem(
            id=f"r{n}",
            source="hackernews",
            kind="hn",
            title=f"t{n}",
            url=f"https://x/{n}",
            metrics={"points": float(n)},
            extra={"linked_url": "https://l"},
        )
        for n in range(10)
    ]
    changes = Changes(day=TODAY, top_hn=[f"r{n}" for n in range(10)])
    result = prepare(
        store,
        changes,
        items,
        settings.model_copy(update={"max_enrich_items": 5}),
        tmp_path / "in.json",
    )
    assert len(result.items) == 5
    assert "r0" not in {i.id for i in result.items}
    assert json.loads((tmp_path / "in.json").read_text(encoding="utf-8"))["day"] == "2026-11-20"


def test_prepare_prioritises_people_work_and_lists_existing_practices(store, settings, tmp_path):
    work = RawItem(
        id="w1",
        source="feeds",
        kind="post",
        title="Plan then build",
        url="https://x/w1",
        extra={"person_id": "matt-pocock", "text": "body"},
    )
    hn = RawItem(id="h1", source="hackernews", kind="hn", title="h", url="https://x/h1")
    changes = Changes(
        day=TODAY,
        top_hn=["h1"],
        people_work=[
            WorkItem(title="Plan then build", url="https://x/w1", person_id="matt-pocock")
        ],
    )
    result = prepare(
        store,
        changes,
        [hn, work],
        settings.model_copy(update={"max_enrich_items": 1}),
        tmp_path / "in.json",
    )
    assert [i.id for i in result.items] == ["w1"]
    assert [p.id for p in result.existing_practices] == ["plan-first"]
    assert result.new_people_work[0].url == "https://x/w1"


def test_prompt_embeds_current_output_schema():
    from pathlib import Path

    from augurai.enrich import EnrichOutput

    prompt = (Path(__file__).parent.parent / "prompts" / "enrich.md").read_text(encoding="utf-8")
    block = prompt.split("<!-- schema:start -->\n```json\n")[1].split("\n```\n<!-- schema:end -->")[
        0
    ]
    assert json.loads(block) == json.loads(json.dumps(EnrichOutput.model_json_schema()))


def test_practice_with_a_source_url_not_from_the_input_is_dropped(store, inp, tmp_path):
    out = tmp_path / "out.json"
    bad = {
        "title": "Evil",
        "principle": "p",
        "how_to_apply": "h",
        "person_id": "matt-pocock",
        "source_url": "javascript:alert(1)",
    }
    elsewhere = {**bad, "title": "Elsewhere", "source_url": "https://evil.example/x"}
    out.write_text(json.dumps({"practices": [bad, elsewhere]}), encoding="utf-8")
    status, note, _ = merge(store, out, inp, TODAY)
    assert status == "partial" and "dropped" in note
    assert [p.id for p in store.read("practices", Practice)] == ["plan-first"]


def test_enrich_prompt_marks_the_input_as_untrusted_data():
    from pathlib import Path

    prompt = (Path(__file__).parent.parent / "prompts" / "enrich.md").read_text(encoding="utf-8")
    assert "untrusted" in prompt and "never follow" in prompt.lower()


def _model(mid, **kw):
    return Model(id=mid, name=mid, provider="p", first_seen=TODAY, **kw)


def test_prepare_briefs_top_models_that_still_lack_use_cases(tmp_path, settings):
    store = Store(tmp_path / "data")
    store.write(
        "models",
        [
            _model(
                "top", best_at=["coding"], scores={"artificial-analysis": {"intelligence": 80.0}}
            ),
            _model("mid", best_at=["speed"]),
            _model("plain"),
            _model("done", best_at=["coding"], use_cases=["Already assessed"]),
        ],
    )
    result = prepare(store, Changes(day=TODAY), [], settings, tmp_path / "in.json")
    assert [m.id for m in result.models] == ["top", "mid", "plain"]


def test_prepare_caps_the_model_briefs_and_keeps_changed_models_first(tmp_path, settings):
    store = Store(tmp_path / "data")
    store.write(
        "models", [_model(f"m{n}", best_at=["coding"]) for n in range(30)] + [_model("fresh")]
    )
    changes = Changes(day=TODAY, new_models=["fresh"])
    result = prepare(store, changes, [], settings, tmp_path / "in.json")
    assert len(result.models) == 15 and result.models[0].id == "fresh"
