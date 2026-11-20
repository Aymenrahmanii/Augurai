import json
from datetime import UTC, datetime

import httpx
import respx

from augurai import mailer
from augurai.coach.run import load_env_file, run_coach

NOW = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
ENV = {"GMAIL_USER": "me@example.com", "GMAIL_APP_PASSWORD": "pw", "BRIEFING_TO": "to@example.com"}
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
def test_run_coach_dry_run_writes_report_without_email(
    tmp_path, fixture_path, settings, monkeypatch
):
    respx.get(settings.site_url + "data/practices.json").respond(404)
    sent = []
    monkeypatch.setattr(mailer, "send", lambda msg, env: sent.append(msg) or True)
    prompts = []

    def runner(args, stdin):
        prompts.append(stdin)
        return REPLY

    home = make_home(tmp_path, fixture_path)
    since_now = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
    path = run_coach(
        root=tmp_path / "repo",
        settings=settings,
        now=since_now,
        days=7,
        dry_run=True,
        env=ENV,
        home=home,
        runner=runner,
        http=httpx.Client(),
    )
    assert path.exists() and path.parent == tmp_path / "repo" / "coach" / "proposals"
    assert sent == []
    assert "sk-ant" not in prompts[0] and "tdd" in prompts[0]  # redacted, skills listed
    assert "{{PROFILE}}" not in prompts[0] and "{{PRACTICES}}" not in prompts[0]


@respx.mock
def test_run_coach_emails_when_not_dry_run(tmp_path, fixture_path, settings, monkeypatch):
    respx.get(settings.site_url + "data/practices.json").respond(404)
    sent = []
    monkeypatch.setattr(mailer, "send", lambda msg, env: sent.append(msg) or True)
    run_coach(
        root=tmp_path / "repo",
        settings=settings,
        now=NOW,
        days=7,
        dry_run=False,
        env=ENV,
        home=make_home(tmp_path, fixture_path),
        runner=lambda args, stdin: REPLY,
        http=httpx.Client(),
    )
    assert len(sent) == 1 and "Augurai coach" in sent[0]["Subject"]


def test_load_env_file_parses_simple_pairs(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        '# comment\nGMAIL_USER=me@example.com\nBRIEFING_TO="to@example.com"\n\nBAD LINE\n',
        encoding="utf-8",
    )
    assert load_env_file(path) == {"GMAIL_USER": "me@example.com", "BRIEFING_TO": "to@example.com"}
    assert load_env_file(tmp_path / "missing") == {}


def test_coach_prompt_embeds_current_proposals_schema():
    from pathlib import Path

    from augurai.coach.propose import Proposals

    prompt = (Path(__file__).parents[2] / "prompts" / "coach.md").read_text(encoding="utf-8")
    block = prompt.split("<!-- schema:start -->\n```json\n")[1].split("\n```\n<!-- schema:end -->")[
        0
    ]
    assert json.loads(block) == json.loads(json.dumps(Proposals.model_json_schema()))
