"""Read Claude Code session transcripts (~/.claude/projects/**/*.jsonl) into compact summaries."""

import json
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from augurai.coach.redact import redact

PROMPT_LIMIT = 300
COMMAND_LIMIT = 120
_SLASH = re.compile(r"<command-name>(/[^<\s]+)</command-name>")
_NOT_PROMPTS = (
    "<command-",
    "<local-command",
    "<system-reminder",
    "Caveat:",
    "[Request interrupted",
)
_SHELL_TOOLS = {"Bash", "PowerShell"}


@dataclass
class SessionSummary:
    project: str
    session_id: str
    started: datetime
    ended: datetime
    user_prompts: list[str] = field(default_factory=list)
    tool_counts: dict[str, int] = field(default_factory=dict)
    skills_used: list[str] = field(default_factory=list)
    slash_commands: list[str] = field(default_factory=list)
    bash_commands: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _clip(text: str, limit: int) -> str:
    return redact(text.strip())[:limit]


def _parse(path: Path, project: str) -> SessionSummary | None:
    stamps: list[datetime] = []
    prompts: list[str] = []
    tools: Counter[str] = Counter()
    skills: list[str] = []
    slashes: list[str] = []
    commands: list[str] = []
    events: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("timestamp"), str):
            try:
                stamps.append(datetime.fromisoformat(row["timestamp"]))
            except ValueError:
                pass
        message = row.get("message") or {}
        if row.get("type") == "user" and not row.get("isMeta") and not row.get("isSidechain"):
            text = _text(message.get("content"))
            slashes += _SLASH.findall(text)
            if text.strip() and not text.lstrip().startswith(_NOT_PROMPTS):
                prompts.append(_clip(text, PROMPT_LIMIT))
        elif row.get("type") == "assistant" and isinstance(message.get("content"), list):
            for block in message["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                name = str(block.get("name", ""))
                payload = block.get("input") or {}
                tools[name] += 1
                if name == "Skill":
                    skill = str(payload.get("skill", ""))
                    skills.append(skill)
                    events.append(f"Skill:{skill}")
                elif name in {"Edit", "Write", "EnterPlanMode", "Agent", *_SHELL_TOOLS}:
                    events.append("Bash" if name in _SHELL_TOOLS else name)
                    if name in _SHELL_TOOLS and payload.get("command"):
                        commands.append(_clip(str(payload["command"]), COMMAND_LIMIT))
    if not stamps:
        return None
    return SessionSummary(
        project=project,
        session_id=path.stem,
        started=min(stamps),
        ended=max(stamps),
        user_prompts=prompts,
        tool_counts=dict(tools),
        skills_used=skills,
        slash_commands=slashes,
        bash_commands=commands,
        events=events,
    )


def iter_sessions(projects_dir: Path, since: datetime) -> Iterator[SessionSummary]:
    for path in sorted(projects_dir.rglob("*.jsonl")):
        project = path.relative_to(projects_dir).parts[0]
        summary = _parse(path, project)
        if summary is not None and summary.ended >= since:
            yield summary
