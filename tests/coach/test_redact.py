from augurai.coach.redact import redact


def test_redacts_keys_and_keeps_names():
    out = redact("ANTHROPIC token=sk-ant-abc123def456ghi and api_key: hunter2")
    assert "sk-ant" not in out and "hunter2" not in out and "api_key" in out


def test_redacts_github_and_aws_tokens():
    out = redact("ghp_" + "a" * 36 + " github_pat_" + "B" * 30 + " AKIA" + "Z" * 16)
    assert out.count("[REDACTED]") == 3


def test_redacts_emails_and_long_blobs():
    out = redact("mail me at someone@example.com or use " + "x" * 40)
    assert "someone@example.com" not in out and "x" * 32 not in out


def test_leaves_normal_text_alone():
    text = "Plan the radar feature, then run uv run pytest -q."
    assert redact(text) == text


def test_password_value_only_is_redacted():
    assert redact("password = s3cr3t!") == "password = [REDACTED]"
