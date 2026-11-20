from datetime import datetime

import httpx

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsSource:
    name = "hackernews"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        minimum = ctx.settings.hn_min_points
        items: dict[str, RawItem] = {}
        errors: list[str] = []
        for query in ctx.settings.hn_queries:
            try:
                response = ctx.http.get(
                    URL,
                    params={
                        "tags": "story",
                        "numericFilters": f"points>{minimum}",
                        "query": query,
                        "hitsPerPage": 30,
                    },
                )
                response.raise_for_status()
                hits = response.json().get("hits", [])
            except httpx.HTTPError as exc:
                errors.append(f"{query}: {exc}")
                continue
            for hit in hits:
                points = hit.get("points") or 0
                if points < minimum:
                    continue
                url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
                items.setdefault(
                    url,
                    RawItem(
                        id=RawItem.make_id(url),
                        source=self.name,
                        kind="hn",
                        title=hit.get("title") or "",
                        url=url,
                        author=hit.get("author"),
                        published=datetime.fromisoformat(hit["created_at"]),
                        metrics={
                            "points": float(points),
                            "comments": float(hit.get("num_comments") or 0),
                        },
                        extra={"linked_url": hit.get("url")},
                    ),
                )
        if errors and not items:
            raise SourceError("; ".join(errors)[:300])
        return list(items.values())
