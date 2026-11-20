"""JSON-file store for data/<collection>.json with stable, diff-friendly output."""

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Store:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, collection: str) -> Path:
        return self.root / f"{collection}.json"

    def read(self, collection: str, model: type[T]) -> list[T]:
        path = self._path(collection)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [model.model_validate(item) for item in raw]

    def read_map(self, collection: str, model: type[T]) -> dict[str, T]:
        return {item.id: item for item in self.read(collection, model)}  # type: ignore[attr-defined]

    def write(self, collection: str, items: Iterable[BaseModel]) -> bool:
        rows = sorted((i.model_dump(mode="json") for i in items), key=lambda r: str(r["id"]))
        text = json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        path = self._path(collection)
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
        return True
