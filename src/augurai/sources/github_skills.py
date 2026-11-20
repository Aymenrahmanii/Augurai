import httpx

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError
from augurai.sources.github_common import repo_item, search_repositories

SKILL_TOPICS = ("claude-code-skills", "agent-skills")


class GitHubSkillsSource:
    name = "github-skills"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        items: dict[str, RawItem] = {}
        errors: list[str] = []
        for topic in SKILL_TOPICS:
            try:
                rows = search_repositories(ctx, f"topic:{topic}")
            except httpx.HTTPError as exc:
                errors.append(f"{topic}: {exc}")
                continue
            for row in rows:
                item = repo_item(row, self.name, "skill")
                items.setdefault(item.id, item)
        if errors and not items:
            raise SourceError("; ".join(errors)[:300])
        return list(items.values())
