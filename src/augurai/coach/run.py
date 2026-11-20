"""The weekly coach: read local sessions, ask Claude, write private proposals."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from augurai.coach import report
from augurai.coach.profile import build_profile
from augurai.coach.propose import Runner, default_runner, load_practices, parse, run_claude
from augurai.coach.transcripts import iter_sessions
from augurai.config import Settings
from augurai.timeutil import iso_week, local_date

PROMPT_FILE = Path(__file__).resolve().parents[3] / "prompts" / "coach.md"


def _render_prompt(profile_json: str, practices_json: str) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")
    return template.replace("{{PROFILE}}", profile_json).replace("{{PRACTICES}}", practices_json)


def run_coach(
    root: Path,
    settings: Settings,
    now: datetime,
    days: int,
    home: Path | None = None,
    runner: Runner = default_runner,
    http: httpx.Client | None = None,
) -> Path:
    home = home or Path.home()
    claude_dir = home / ".claude"
    week = iso_week(local_date(now, settings.timezone))
    sessions = list(iter_sessions(claude_dir / "projects", now - timedelta(days=days)))
    claude_md_path = claude_dir / "CLAUDE.md"
    claude_md = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
    skills_dir = claude_dir / "skills"
    installed = [p.name for p in skills_dir.iterdir() if p.is_dir()] if skills_dir.exists() else []
    profile = build_profile(sessions, claude_md, installed, week)

    practices = load_practices(settings, root, http or httpx.Client())
    practices_json = json.dumps(
        [
            p.model_dump(
                mode="json", include={"id", "title", "principle", "how_to_apply", "person_id"}
            )
            for p in practices
        ],
        indent=2,
    )
    prompt = _render_prompt(profile.model_dump_json(indent=2), practices_json)
    answer = run_claude(prompt, runner=runner)
    proposals = parse(answer, week, {p.id for p in practices})
    path = report.write(proposals, root)
    return path
