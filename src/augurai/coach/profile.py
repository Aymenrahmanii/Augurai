"""Condense a week of sessions into an activity profile the coach can reason about."""

import re
from collections import Counter

from pydantic import BaseModel, Field

from augurai.coach.redact import redact
from augurai.coach.transcripts import SessionSummary

MAX_SAMPLE_PROMPTS = 40
MAX_CLAUDE_MD = 4000
_PLANNING_SKILLS = (
    "brainstorming",
    "grill-me",
    "grill-with-docs",
    "grilling",
    "to-spec",
    "writing-plans",
)
_BUILD_EVENTS = {"Edit", "Write"}
_TESTS = re.compile(r"pytest|npm test|uv run pytest")
_COMMIT = re.compile(r"git commit")


class ActivityProfile(BaseModel):
    week: str
    sessions: int
    total_prompts: int
    tool_counts: dict[str, int] = Field(default_factory=dict)
    skills_used: dict[str, int] = Field(default_factory=dict)
    signals: dict[str, float] = Field(default_factory=dict)
    sample_prompts: list[str] = Field(default_factory=list)
    claude_md: str = ""
    installed_skills: list[str] = Field(default_factory=list)


def _is_planning(event: str) -> bool:
    return event == "EnterPlanMode" or (
        event.startswith("Skill:") and event.split(":")[-1] in _PLANNING_SKILLS
    )


def _planned_before_building(events: list[str]) -> bool:
    for event in events:
        if _is_planning(event):
            return True
        if event in _BUILD_EVENTS:
            return False
    return False


def _fraction(flags: list[bool]) -> float:
    return sum(flags) / len(flags) if flags else 0.0


def _sample(sessions: list[SessionSummary]) -> list[str]:
    ordered = sorted(sessions, key=lambda s: s.started, reverse=True)
    samples: list[str] = []
    depth = 0
    while len(samples) < MAX_SAMPLE_PROMPTS and any(len(s.user_prompts) > depth for s in ordered):
        for session in ordered:
            if len(session.user_prompts) > depth and len(samples) < MAX_SAMPLE_PROMPTS:
                samples.append(session.user_prompts[depth])
        depth += 1
    return samples


def build_profile(
    sessions: list[SessionSummary], claude_md: str, installed_skills: list[str], week: str
) -> ActivityProfile:
    tools: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    for session in sessions:
        tools.update(session.tool_counts)
        skills.update(session.skills_used)
    signals = {
        "planned_before_building": _fraction(
            [_planned_before_building(s.events) for s in sessions]
        ),
        "ran_tests": _fraction([any(_TESTS.search(c) for c in s.bash_commands) for s in sessions]),
        "used_subagents": _fraction(["Agent" in s.events for s in sessions]),
        "committed": _fraction([any(_COMMIT.search(c) for c in s.bash_commands) for s in sessions]),
    }
    return ActivityProfile(
        week=week,
        sessions=len(sessions),
        total_prompts=sum(len(s.user_prompts) for s in sessions),
        tool_counts=dict(tools),
        skills_used=dict(skills),
        signals=signals,
        sample_prompts=[redact(p) for p in _sample(sessions)],
        claude_md=redact(claude_md)[:MAX_CLAUDE_MD],
        installed_skills=sorted(installed_skills),
    )
