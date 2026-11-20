"""Regenerate the JSON schema blocks embedded in prompts/*.md. Run: uv run python scripts/render_prompts.py"""

import json
import re
from pathlib import Path

from augurai.enrich import EnrichOutput

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
BLOCK = re.compile(
    r"(<!-- schema:start -->\n```json\n)(.*?)(\n```\n<!-- schema:end -->)", re.DOTALL
)


def schema_text() -> str:
    return json.dumps(EnrichOutput.model_json_schema(), indent=2, sort_keys=True)


def main() -> None:
    path = PROMPTS / "enrich.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        BLOCK.sub(lambda m: m.group(1) + schema_text() + m.group(3), text), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
