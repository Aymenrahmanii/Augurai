import json
from datetime import UTC, datetime

import httpx
import respx

from augurai.coach.run import run_coach

NOW = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
REPLY = json.dumps(
    {
        "result": json.dumps(
            {
                "items": [
                    {
                        "observation": "o",
                        "practice_id": None,
                        "person": None,
                        "change_kind": "habit",
                        "change": "c",
                        "apply": "a",
                    }
                ]
            }
        )
    }
)


def make_home(tmp_path, fixture_path):
    home = tmp_path / "home"
    (home / ".claude" / "projects" / "proj").mkdir(parents=True)
    (home / ".claude" / "skills" / "tdd").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text(
        "# My rules\ntoken=sk-ant-abc123def456ghi", encoding="utf-8"
    )
    session = fixture_path("coach/synthetic_session.jsonl").read_text(encoding="utf-8")
    (home / ".claude" / "projects" / "proj" / "s.jsonl").write_text(session, encoding="utf-8")
    return home


@respx.mock
def test_run_coach_writes_the_private_report(tmp_path, fixture_path, settings):
    respx.get(settings.site_url + "data/practices.json").respond(404)
    prompts = []

    def runner(args, stdin):
        prompts.append(stdin)
        return REPLY

    path = run_coach(
        root=tmp_path / "repo",
        settings=settings,
        now=NOW,
        days=7,
        home=make_home(tmp_path, fixture_path),
        runner=runner,
        http=httpx.Client(),
    )
    assert path.exists() and path.parent == tmp_path / "repo" / "coach" / "proposals"
    assert "sk-ant" not in prompts[0] and "tdd" in prompts[0]  # redacted, skills listed
    assert "{{PROFILE}}" not in prompts[0] and "{{PRACTICES}}" not in prompts[0]


def test_coach_prompt_embeds_current_proposals_schema():
    from pathlib import Path

    from augurai.coach.propose import Proposals

    prompt = (Path(__file__).parents[2] / "prompts" / "coach.md").read_text(encoding="utf-8")
    block = prompt.split("<!-- schema:start -->\n```json\n")[1].split("\n```\n<!-- schema:end -->")[
        0
    ]
    assert json.loads(block) == json.loads(json.dumps(Proposals.model_json_schema()))
