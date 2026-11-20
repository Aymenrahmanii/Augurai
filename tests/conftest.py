import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from augurai.config import load_settings
from augurai.sources.base import SourceContext

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 20, 5, 0, tzinfo=UTC)


@pytest.fixture
def fixture_path():
    return lambda name: FIXTURES / name


@pytest.fixture
def fixture():
    def load(name: str):
        text = (FIXTURES / name).read_text(encoding="utf-8")
        return json.loads(text) if name.endswith(".json") else text

    return load


@pytest.fixture
def settings():
    return load_settings(Path(__file__).parent.parent / "config" / "augurai.toml")


@pytest.fixture
def ctx(settings):
    return SourceContext(settings=settings, http=httpx.Client(), now=NOW, env={})
