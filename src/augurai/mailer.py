"""Render and send the briefing email; guard against sending twice for the same local date."""

import smtplib
from collections.abc import Mapping
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from augurai.briefing import Briefing
from augurai.config import Settings
from augurai.mdhtml import render_markdown
from augurai.models import RunRecord
from augurai.store import Store
from augurai.timeutil import local_date

TEMPLATES = Path(__file__).parent / "site" / "templates"
SUBJECT_HEADLINE_LIMIT = 90
REQUIRED_ENV = ("GMAIL_USER", "GMAIL_APP_PASSWORD", "BRIEFING_TO")


def already_sent(root: Path, day: date, tz: str = "Africa/Tunis") -> bool:
    runs = Store(root / "data").read("runs", RunRecord)
    return any(
        r.mode == "morning" and r.email_sent and local_date(r.started, tz) == day for r in runs
    )


def render_message(subject: str, markdown: str, title: str, settings: Settings) -> EmailMessage:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    html = env.get_template("email.html").render(
        title=title, body=render_markdown(markdown), site_url=settings.site_url
    )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg.set_content(markdown)
    msg.add_alternative(html, subtype="html")
    return msg


def render(briefing: Briefing, settings: Settings) -> EmailMessage:
    headline = briefing.headline[:SUBJECT_HEADLINE_LIMIT]
    subject = f"Augurai · {briefing.day:%a %d %b} · {headline}"
    return render_message(subject, briefing.markdown, briefing.headline, settings)


def send(msg: EmailMessage, env: Mapping[str, str]) -> bool:
    if any(not env.get(name) for name in REQUIRED_ENV):
        return False
    for header in ("From", "To"):
        del msg[header]
    msg["From"] = env["GMAIL_USER"]
    msg["To"] = env["BRIEFING_TO"]
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(env["GMAIL_USER"], env["GMAIL_APP_PASSWORD"])
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError):
        return False
    return True
