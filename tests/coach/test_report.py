from augurai import mailer
from augurai.coach.propose import Proposal, Proposals
from augurai.coach.report import email, write

ITEM = Proposal(
    observation="You started building before planning in 4 of 5 sessions",
    practice_id="plan-first",
    person="Matt Pocock",
    change_kind="skill_use",
    change="Start each feature with /grill-me",
    apply="/grill-me",
)
ENV = {"GMAIL_USER": "me@example.com", "GMAIL_APP_PASSWORD": "pw", "BRIEFING_TO": "to@example.com"}


def proposals(n: int = 2) -> Proposals:
    return Proposals(week="2026-W47", items=[ITEM] * n)


def test_report_written_under_gitignored_dir(tmp_path):
    path = write(proposals(), tmp_path)
    assert path == tmp_path / "coach" / "proposals" / "2026-W47.md"
    assert path.exists()


def test_report_has_numbered_sections_with_apply_step(tmp_path):
    text = write(proposals(2), tmp_path).read_text(encoding="utf-8")
    assert "## 1." in text and "## 2." in text
    assert "You started building before planning" in text
    assert "Matt Pocock" in text and "`/grill-me`" in text


def test_email_subject_and_send(monkeypatch, settings):
    sent = {}

    def fake_send(msg, env):
        sent["msg"], sent["env"] = msg, env
        return True

    monkeypatch.setattr(mailer, "send", fake_send)
    assert email(proposals(3), settings, ENV) is True
    assert sent["msg"]["Subject"] == "Augurai coach · 2026-W47 · 3 suggestions"
    assert "<h2>" in sent["msg"].get_body(("html",)).get_content()


def test_email_singular_subject(monkeypatch, settings):
    monkeypatch.setattr(mailer, "send", lambda msg, env: True)
    captured = {}
    monkeypatch.setattr(
        mailer, "send", lambda msg, env: captured.setdefault("s", msg["Subject"]) or True
    )
    email(proposals(1), settings, ENV)
    assert captured["s"].endswith("1 suggestion")
