import json

import httpx
import pytest
import respx

from augurai.coach.propose import Proposals, load_practices, parse, run_claude

VALID_ITEM = {
    "observation": "You started building before planning in 4 of 5 sessions",
    "practice_id": "plan-first",
    "person": "Matt Pocock",
    "change_kind": "skill_use",
    "change": "Start each feature with /grill-me",
    "apply": "/grill-me",
}
WEEK = "2026-W47"


def envelope(payload: dict) -> str:
    return json.dumps({"type": "result", "result": json.dumps(payload)})


def test_parse_unwraps_envelope_and_drops_unknown_practice():
    raw = envelope({"week": WEEK, "items": [VALID_ITEM | {"practice_id": "nope"}]})
    proposals = parse(raw, WEEK, {"plan-first"})
    assert isinstance(proposals, Proposals)
    assert proposals.items[0].practice_id is None


def test_parse_keeps_known_practice():
    raw = envelope({"week": WEEK, "items": [VALID_ITEM]})
    assert parse(raw, WEEK, {"plan-first"}).items[0].practice_id == "plan-first"


def test_parse_rejects_empty():
    with pytest.raises(ValueError, match="no valid"):
        parse('{"week": "2026-W47", "items": []}', WEEK, set())


def test_parse_drops_invalid_items_but_keeps_valid_ones():
    raw = json.dumps({"items": [{"observation": "incomplete"}, VALID_ITEM]})
    assert len(parse(raw, WEEK, set()).items) == 1


def test_parse_caps_at_five_items():
    raw = json.dumps({"items": [VALID_ITEM] * 8})
    assert len(parse(raw, WEEK, set()).items) == 5


def test_parse_finds_json_inside_prose_and_overrides_week():
    text = "Sure, here you go:\n" + json.dumps({"week": "wrong", "items": [VALID_ITEM]}) + "\nBye"
    assert parse(text, WEEK, set()).week == WEEK


def test_parse_rejects_non_json():
    with pytest.raises(ValueError):
        parse("I could not do that.", WEEK, set())


def test_run_claude_passes_prompt_on_stdin_with_print_flags():
    seen = {}

    def runner(args, stdin):
        seen["args"], seen["stdin"] = args, stdin
        return "ok"

    assert run_claude("hello", runner=runner) == "ok"
    assert "-p" in seen["args"] and "json" in seen["args"] and seen["stdin"] == "hello"


@respx.mock
def test_load_practices_from_site(settings, tmp_path):
    data = [
        {
            "id": "plan-first",
            "title": "Plan first",
            "principle": "p",
            "how_to_apply": "h",
            "person_id": "matt-pocock",
            "source_url": "https://x",
            "first_seen": "2026-11-20",
        }
    ]
    respx.get(settings.site_url + "data/practices.json").respond(json=data)
    practices = load_practices(settings, tmp_path, httpx.Client())
    assert [p.id for p in practices] == ["plan-first"]


@respx.mock
def test_load_practices_falls_back_to_local_file_then_empty(settings, tmp_path):
    respx.get(settings.site_url + "data/practices.json").respond(404)
    assert load_practices(settings, tmp_path, httpx.Client()) == []
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "practices.json").write_text(
        json.dumps(
            [
                {
                    "id": "local",
                    "title": "t",
                    "principle": "p",
                    "how_to_apply": "h",
                    "person_id": "x",
                    "source_url": "https://x",
                    "first_seen": "2026-11-20",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert [p.id for p in load_practices(settings, tmp_path, httpx.Client())] == ["local"]
