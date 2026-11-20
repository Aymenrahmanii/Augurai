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


def test_redacts_env_var_forms_quoted_json_bearer_and_urls():
    for text in (
        "GMAIL_APP_PASSWORD=hunter2hunter2",
        'export OPENAI_API_KEY="abcd1234abcd"',
        '{"api_key": "abcd1234"}',
        "Authorization: Bearer abc123def456",
        "postgres://admin:S3cretPw@localhost:5432/db",
        "CLAUDE_CODE_OAUTH_TOKEN: tok_abc123",
    ):
        out = redact(text)
        secrets = ("hunter2hunter2", "abcd1234", "abc123def456", "S3cretPw", "tok_abc123")
        assert not any(s in out for s in secrets), out


def test_keeps_names_around_redacted_env_values():
    out = redact("GMAIL_USER=me GMAIL_APP_PASSWORD=secret123")
    assert "GMAIL_APP_PASSWORD" in out and "secret123" not in out
