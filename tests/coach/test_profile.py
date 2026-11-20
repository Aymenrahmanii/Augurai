from datetime import UTC, datetime

from augurai.coach.profile import build_profile
from augurai.coach.transcripts import SessionSummary

T = datetime(2026, 11, 18, tzinfo=UTC)


def session(events=(), bash=(), prompts=("hi",), skills=(), sid="s") -> SessionSummary:
    return SessionSummary(
        project="p",
        session_id=sid,
        started=T,
        ended=T,
        user_prompts=list(prompts),
        tool_counts={},
        skills_used=list(skills),
        slash_commands=[],
        bash_commands=list(bash),
        events=list(events),
    )


def signals(sessions):
    return build_profile(sessions, "", [], "2026-W47").signals


def test_planned_before_building_signal():
    planned = session(["Skill:superpowers:brainstorming", "Edit"])
    unplanned = session(["Edit", "Skill:superpowers:brainstorming"])
    assert signals([planned, unplanned])["planned_before_building"] == 0.5


def test_plan_mode_counts_as_planning_and_no_edit_means_plan_only():
    assert signals([session(["EnterPlanMode", "Edit"])])["planned_before_building"] == 1.0
    assert signals([session(["Skill:grill-me"])])["planned_before_building"] == 1.0
    assert signals([session(["Bash"])])["planned_before_building"] == 0.0


def test_other_signals():
    s = session(["Agent"], bash=["uv run pytest -q", "git commit -m x"])
    sig = signals([s, session()])
    assert sig["ran_tests"] == 0.5 and sig["used_subagents"] == 0.5 and sig["committed"] == 0.5


def test_no_sessions_gives_zero_signals():
    profile = build_profile([], "", [], "2026-W47")
    assert profile.sessions == 0 and all(v == 0.0 for v in profile.signals.values())


def test_profile_aggregates_and_limits():
    sessions = [
        session(prompts=[f"prompt {n}-{m}" for m in range(5)], skills=["a"], sid=str(n))
        for n in range(30)
    ]
    profile = build_profile(sessions, "x" * 9000, ["tdd", "grilling"], "2026-W47")
    assert profile.sessions == 30 and profile.total_prompts == 150
    assert len(profile.sample_prompts) <= 40
    assert len(profile.claude_md) <= 4000
    assert profile.skills_used == {"a": 30}
    assert profile.installed_skills == ["grilling", "tdd"]


def test_profile_redacts_claude_md():
    profile = build_profile([], "token=sk-ant-abc123def456ghi", [], "2026-W47")
    assert "sk-ant" not in profile.claude_md
