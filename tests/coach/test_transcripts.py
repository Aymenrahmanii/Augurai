from datetime import UTC, datetime

from augurai.coach.transcripts import iter_sessions

SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def make_project(tmp_path, fixture_path, extra: str = ""):
    project = tmp_path / "C--Users-x-project"
    project.mkdir()
    text = fixture_path("coach/synthetic_session.jsonl").read_text(encoding="utf-8")
    (project / "abc.jsonl").write_text(text + extra, encoding="utf-8")
    return tmp_path


def test_parses_synthetic_session(tmp_path, fixture_path):
    sessions = list(iter_sessions(make_project(tmp_path, fixture_path), SINCE))
    assert len(sessions) == 1
    s = sessions[0]
    assert s.project == "C--Users-x-project" and s.session_id == "abc"
    assert s.started < s.ended
    assert s.tool_counts == {"Skill": 1, "Edit": 1, "Bash": 2, "Agent": 1}
    assert s.skills_used == ["superpowers:brainstorming"]
    assert s.slash_commands == ["/model"]
    assert s.events == ["Skill:superpowers:brainstorming", "Edit", "Bash", "Bash", "Agent"]
    assert s.bash_commands == ["uv run pytest -q", "git commit -m 'feat: x'"]


def test_prompts_exclude_meta_and_commands_and_redact_secrets(tmp_path, fixture_path):
    s = next(iter_sessions(make_project(tmp_path, fixture_path), SINCE))
    assert s.user_prompts == [
        "Plan the radar feature. my key is [REDACTED]",
        "Now fix the failing test please",
    ]


def test_skips_malformed_lines(tmp_path, fixture_path):
    root = make_project(tmp_path, fixture_path, extra="\n{not json\n\n[1, 2]\n")
    assert len(list(iter_sessions(root, SINCE))) == 1


def test_huge_prompt_is_truncated(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    line = (
        '{"type":"user","timestamp":"2026-11-18T10:00:00.000Z","message":{"role":"user","content":"'
        + "word " * 10000
        + '"}}\n'
    )
    (project / "s.jsonl").write_text(line, encoding="utf-8")
    s = next(iter_sessions(tmp_path, SINCE))
    assert len(s.user_prompts[0]) <= 300


def test_sessions_before_since_are_skipped(tmp_path, fixture_path):
    root = make_project(tmp_path, fixture_path)
    assert list(iter_sessions(root, datetime(2026, 12, 1, tzinfo=UTC))) == []


def test_sidechain_messages_are_not_user_prompts(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    row = {
        "type": "user",
        "isSidechain": True,
        "timestamp": "2026-11-18T10:00:00.000Z",
        "message": {"role": "user", "content": "subagent instruction"},
    }
    import json

    (project / "s.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert next(iter_sessions(tmp_path, SINCE)).user_prompts == []
