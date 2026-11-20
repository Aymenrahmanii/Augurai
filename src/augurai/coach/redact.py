"""Strip secrets from text before it leaves the machine."""

import re

MARK = "[REDACTED]"
_TOKENS = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{10,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AKIA[0-9A-Z]{16}"
)
# NAME=value, NAME: value, "name": "value", including names such as GMAIL_APP_PASSWORD.
_KEY_VALUE = re.compile(
    r"""(?i)([A-Za-z0-9_]*(?:api[_-]?key|token|secret|password|passwd|pwd)["']?\s*[:=]\s*["']?)[^\s"',}]+"""
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_URL_CREDENTIALS = re.compile(r"(://[^:/\s@]+:)[^@\s]+(@)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_BLOB = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


def redact(text: str) -> str:
    text = _TOKENS.sub(MARK, text)
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{MARK}", text)
    text = _BEARER.sub(f"Bearer {MARK}", text)
    text = _URL_CREDENTIALS.sub(lambda m: f"{m.group(1)}{MARK}{m.group(2)}", text)
    text = _EMAIL.sub(MARK, text)
    return _BLOB.sub(MARK, text)
