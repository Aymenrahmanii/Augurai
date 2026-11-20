from datetime import timedelta

import httpx

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError
from augurai.sources.github_common import repo_item, search_repositories


class GitHubReposSource:
    name = "github-repos"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        since = (ctx.now - timedelta(days=30)).date().isoformat()
        items: dict[str, RawItem] = {}
        errors: list[str] = []
        for topic in ctx.settings.github_topics:
            kind = "agent" if topic == "ai-agents" else "repo"
            try:
                rows = search_repositories(ctx, f"topic:{topic} created:>{since}")
            except httpx.HTTPError as exc:
                errors.append(f"{topic}: {exc}")
                continue
            for row in rows:
                item = repo_item(row, self.name, kind)
                items.setdefault(item.id, item)
        if errors and not items:
            raise SourceError("; ".join(errors)[:300])
        return list(items.values())
