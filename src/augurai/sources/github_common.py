"""Shared helpers for GitHub repository-search based sources."""

from datetime import datetime

from augurai.models import ItemKind, RawItem
from augurai.sources.base import SourceContext, github_headers

SEARCH_URL = "https://api.github.com/search/repositories"


def search_repositories(ctx: SourceContext, query: str, per_page: int = 30) -> list[dict]:
    response = ctx.http.get(
        SEARCH_URL,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page},
        headers=github_headers(ctx.env),
    )
    response.raise_for_status()
    items = response.json().get("items")
    return items if isinstance(items, list) else []


def repo_item(row: dict, source: str, kind: ItemKind) -> RawItem:
    url = row["html_url"]
    created = row.get("created_at")
    return RawItem(
        id=RawItem.make_id(url),
        source=source,
        kind=kind,
        title=row["full_name"],
        url=url,
        author=(row.get("owner") or {}).get("login"),
        published=datetime.fromisoformat(created) if created else None,
        metrics={"stars": float(row.get("stargazers_count") or 0)},
        extra={
            "owner": (row.get("owner") or {}).get("login", ""),
            "description": row.get("description") or "",
            "topics": row.get("topics") or [],
        },
    )
