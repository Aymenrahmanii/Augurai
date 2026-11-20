"""Pydantic schemas for every collection stored under data/."""

import hashlib
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

Category = Literal[
    "coding",
    "agentic",
    "reasoning",
    "long_context",
    "multimodal",
    "speed",
    "cost_efficiency",
    "open_weights",
    "engineering",
    "finance",
    "legal",
    "healthcare",
    "strategy",
    "economics",
]
ItemKind = Literal["model", "repo", "skill", "mcp", "agent", "paper", "post", "video", "hn", "job"]
EntityKind = Literal["repo", "skill", "mcp", "agent"]
PersonStatus = Literal["seed", "followed", "rising", "dormant"]
Market = Literal["global", "fr", "tn"]
EnrichmentStatus = Literal["ran", "partial", "failed", "skipped"]


class RawItem(BaseModel):
    id: str
    source: str
    kind: ItemKind
    title: str
    url: str
    author: str | None = None
    published: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def make_id(url: str) -> str:
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
        normalized = urlunsplit(
            (parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
        )
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


class Model(BaseModel):
    id: str
    name: str
    provider: str
    released: date | None = None
    open_weights: bool = False
    context_window: int | None = None
    price_in: float | None = None
    price_out: float | None = None
    modalities: list[str] = Field(default_factory=list)
    scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    best_at: list[Category] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    avoid_for: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)
    first_seen: date


class StarSnapshot(BaseModel):
    day: date
    stars: int


class Entity(BaseModel):
    id: str
    kind: EntityKind
    name: str
    url: str
    owner: str
    owner_type: str = "User"
    description: str = ""
    stars: int = 0
    star_snapshots: list[StarSnapshot] = Field(default_factory=list)
    velocity_7d: float = 0.0
    first_seen: date
    summary: str | None = None


class WorkItem(BaseModel):
    title: str
    url: str
    published: datetime | None = None
    person_id: str


class ScorePoint(BaseModel):
    day: date
    score: float


class Person(BaseModel):
    id: str
    name: str
    links: dict[str, str] = Field(default_factory=dict)
    status: PersonStatus
    score: float = 0.0
    score_history: list[ScorePoint] = Field(default_factory=list)
    above_threshold_runs: int = 0
    why_follow: str = ""
    what_to_learn: str = ""
    recent_work: list[WorkItem] = Field(default_factory=list)
    last_active: date | None = None


class Practice(BaseModel):
    id: str
    title: str
    principle: str
    how_to_apply: str
    person_id: str
    source_url: str
    related_skill: str | None = None
    exercise: str | None = None
    tags: list[str] = Field(default_factory=list)
    first_seen: date
    reinforced_by: list[str] = Field(default_factory=list)


class JobSnapshot(BaseModel):
    id: str
    month: str
    market: Market
    source: str
    total_posts: int
    keyword_counts: dict[str, int]
    notable_roles: list[str] = Field(default_factory=list)


class SourceHealth(BaseModel):
    id: str
    last_success: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class RunRecord(BaseModel):
    id: str
    started: datetime
    mode: Literal["morning", "refresh"]
    sources_ok: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    sources_skipped: list[str] = Field(default_factory=list)
    enrichment: EnrichmentStatus = "skipped"
    enrichment_note: str | None = None
    briefing_written: bool = False


class Summary(BaseModel):
    """LLM summary cached by content hash."""

    id: str
    text: str
