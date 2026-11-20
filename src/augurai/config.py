"""Settings loaded from config/augurai.toml."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class SeedPerson(BaseModel):
    id: str
    name: str
    links: dict[str, str] = Field(default_factory=dict)
    why_follow: str = ""
    what_to_learn: str = ""


class Settings(BaseModel):
    timezone: str = "Africa/Tunis"
    briefing_hour_local: int = 7
    site_url: str = "https://aymenrahmanii.github.io/Augurai/"
    site_base_path: str = "/Augurai/"
    seed_people: list[SeedPerson] = Field(default_factory=list)
    github_topics: list[str] = Field(
        default_factory=lambda: ["llm", "ai-agents", "mcp", "claude-code", "rag", "llmops"]
    )
    hn_queries: list[str] = Field(
        default_factory=lambda: ["LLM", "AI agent", "Claude", "GPT", "MCP", "open-weights"]
    )
    hn_min_points: int = 100
    feeds: list[str] = Field(default_factory=list)
    rising_top_n: int = 10
    promote_threshold: float = 5.0
    promote_consecutive_runs: int = 2
    dormant_days: int = 90
    max_enrich_items: int = 60
    job_keywords: list[str] = Field(
        default_factory=lambda: [
            "LLM",
            "RAG",
            "agents",
            "MCP",
            "fine-tuning",
            "evals",
            "MLOps",
            "PyTorch",
            "LangChain",
            "vector database",
        ]
    )
    adzuna_country: str = "fr"
    tn_job_board: str | None = None


def load_settings(path: Path = Path("config/augurai.toml")) -> Settings:
    with open(path, "rb") as fh:
        return Settings.model_validate(tomllib.load(fh))
