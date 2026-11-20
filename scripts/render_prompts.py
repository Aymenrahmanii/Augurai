"""Regenerate the JSON schema blocks embedded in prompts/*.md. Run: uv run python scripts/render_prompts.py"""

import json
import re
from pathlib import Path

from pydantic import BaseModel

from augurai.coach.propose import Proposals
from augurai.enrich import EnrichOutput

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
BLOCK = re.compile(
    r"(<!-- schema:start -->\n```json\n)(.*?)(\n```\n<!-- schema:end -->)", re.DOTALL
)
SCHEMAS: dict[str, type[BaseModel]] = {"enrich.md": EnrichOutput, "coach.md": Proposals}


def schema_text(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True)


def main() -> None:
    for name, model in SCHEMAS.items():
        path = PROMPTS / name
        text = path.read_text(encoding="utf-8")
        path.write_text(
            BLOCK.sub(lambda m, model=model: m.group(1) + schema_text(model) + m.group(3), text),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
