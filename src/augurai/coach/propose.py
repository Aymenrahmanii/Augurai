"""Ask Claude (headless, local login) for weekly coaching proposals and validate the answer."""

import json
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from augurai.config import Settings
from augurai.models import Practice

MAX_PROPOSALS = 5
DENIED_TOOLS = ("Bash", "Edit", "Write", "WebFetch", "WebSearch")
CLAUDE_TIMEOUT_SECONDS = 600
Runner = Callable[[list[str], str], str]


class Proposal(BaseModel):
    observation: str
    practice_id: str | None = None
    person: str | None = None
    change_kind: Literal["habit", "skill_use", "skill_install", "claude_md"]
    change: str
    apply: str


class Proposals(BaseModel):
    week: str
    items: list[Proposal] = Field(min_length=1, max_length=MAX_PROPOSALS)


def load_practices(settings: Settings, root: Path, http: httpx.Client) -> list[Practice]:
    try:
        response = http.get(settings.site_url + "data/practices.json")
        response.raise_for_status()
        return [Practice.model_validate(p) for p in response.json()]
    except (httpx.HTTPError, ValueError, ValidationError):
        pass
    local = root / "data" / "practices.json"
    if local.exists():
        try:
            return [
                Practice.model_validate(p) for p in json.loads(local.read_text(encoding="utf-8"))
            ]
        except (ValueError, ValidationError):
            return []
    return []


def default_runner(args: list[str], stdin: str) -> str:
    executable = shutil.which(args[0])
    if executable is None:
        raise RuntimeError("the `claude` command was not found on PATH")
    with tempfile.TemporaryDirectory(prefix="augurai-coach-") as scratch:  # no repo files in reach
        result = subprocess.run(
            [executable, *args[1:]],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_TIMEOUT_SECONDS,
            check=False,
            cwd=scratch,
        )
    if result.returncode != 0:
        raise RuntimeError(f"claude exited with {result.returncode}: {result.stderr.strip()[:300]}")
    return result.stdout


def run_claude(prompt: str, runner: Runner = default_runner) -> str:
    args = ["claude", "-p", "--output-format", "json", "--disallowedTools", *DENIED_TOOLS]
    return runner(args, prompt)


def _first_json_object(text: str) -> dict:
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object found in Claude's answer")


def parse(raw: str, week: str, known_practice_ids: set[str]) -> Proposals:
    text = raw
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        outer = None
    if isinstance(outer, dict) and isinstance(outer.get("result"), str):
        text = outer["result"]
    elif isinstance(outer, dict) and "items" in outer:
        text = raw
    payload = _first_json_object(text)
    items: list[Proposal] = []
    for entry in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
        try:
            proposal = Proposal.model_validate(entry)
        except ValidationError:
            continue
        if proposal.practice_id not in known_practice_ids:
            proposal = proposal.model_copy(update={"practice_id": None})
        items.append(proposal)
    if not items:
        raise ValueError("Claude's answer had no valid proposals")
    return Proposals(week=week, items=items[:MAX_PROPOSALS])
