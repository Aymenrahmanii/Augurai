from datetime import UTC, date, datetime
from email.message import EmailMessage

from augurai import mailer
from augurai.briefing import Briefing
from augurai.models import RunRecord
from augurai.store import Store

DAY = date(2026, 11, 20)
ENV = {"GMAIL_USER": "me@example.com", "GMAIL_APP_PASSWORD": "pw", "BRIEFING_TO": "to@example.com"}


def briefing() -> Briefing:
    return Briefing(
        day=DAY,
        headline="Opus takes coding",
        markdown="# Opus takes coding\n\n- <b>x</b>",
        enriched=True,
    )


def test_already_sent_requires_a_morning_run_that_sent(tmp_path):
    root = tmp_path
    assert mailer.already_sent(root, DAY) is False
    store = Store(root / "data")
    run = RunRecord(
        id="r1", started=datetime(2026, 11, 20, 4, 30, tzinfo=UTC), mode="morning", email_sent=False
    )
    store.write("runs", [run])
    assert mailer.already_sent(root, DAY) is False
    store.write("runs", [run.model_copy(update={"email_sent": True})])
    assert mailer.already_sent(root, DAY) is True
    assert mailer.already_sent(root, date(2026, 11, 21)) is False


def test_refresh_runs_do_not_count_as_sent(tmp_path):
    store = Store(tmp_path / "data")
    store.write(
        "runs",
        [
            RunRecord(
                id="r",
                started=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
                mode="refresh",
                email_sent=True,
            )
        ],
    )
    assert mailer.already_sent(tmp_path, DAY) is False


def test_render_has_subject_and_both_parts(settings):
    msg = mailer.render(briefing(), settings)
    assert msg["Subject"] == "Augurai · Fri 20 Nov · Opus takes coding"
    text = msg.get_body(("plain",)).get_content()
    html = msg.get_body(("html",)).get_content()
    assert "Opus takes coding" in text
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html


def test_send_without_env_returns_false():
    assert mailer.send(EmailMessage(), {}) is False


def test_send_uses_smtp_ssl(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host, port):
            calls["host"], calls["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            calls["login"] = (user, password)

        def send_message(self, msg):
            calls["to"] = msg["To"]
            calls["from"] = msg["From"]

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    assert mailer.send(EmailMessage(), ENV) is True
    assert calls["host"] == "smtp.gmail.com" and calls["port"] == 465
    assert calls["login"] == ("me@example.com", "pw")
    assert calls["to"] == "to@example.com" and calls["from"] == "me@example.com"


def test_send_failure_returns_false(monkeypatch):
    def boom(host, port):
        raise OSError("network down")

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", boom)
    assert mailer.send(EmailMessage(), ENV) is False
