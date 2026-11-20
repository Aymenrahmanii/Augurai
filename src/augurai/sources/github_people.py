from datetime import datetime

import httpx

from augurai.models import Person, RawItem
from augurai.sources.base import SourceContext, SourceError, github_headers

# Stronger events replace weaker ones for the same person and repo.
_LABELS = {
    "ReleaseEvent": ("Released", 3),
    "PublicEvent": ("Open-sourced", 3),
    "CreateEvent": ("Created repo", 3),
    "PullRequestEvent": ("Active in", 1),
    "PushEvent": ("Active in", 1),
}


def _login(links: dict[str, str]) -> str | None:
    url = links.get("github")
    return url.rstrip("/").split("/")[-1] if url else None


class GitHubPeopleSource:
    name = "github-people"
    required_env: tuple[str, ...] = ()

    def __init__(self, extra_people: list[Person] | None = None) -> None:
        self.extra_people = extra_people or []

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        people = {p.id: p.links for p in ctx.settings.seed_people}
        people.update({p.id: p.links for p in self.extra_people})
        items: dict[tuple[str, str], tuple[int, RawItem]] = {}
        errors: list[str] = []
        for person_id, links in people.items():
            login = _login(links)
            if not login:
                continue
            try:
                response = ctx.http.get(
                    f"https://api.github.com/users/{login}/events/public",
                    params={"per_page": 30},
                    headers=github_headers(ctx.env),
                )
                response.raise_for_status()
                events = response.json()
            except httpx.HTTPError as exc:
                errors.append(f"{login}: {exc}")
                continue
            for event in events:
                item = self._item(event, person_id)
                if item is None:
                    continue
                rank, raw = item
                key = (person_id, raw.url)
                current = items.get(key)
                if current is None or rank > current[0]:
                    items[key] = (rank, raw)
        if errors and not items:
            raise SourceError("; ".join(errors)[:300])
        return [raw for _, raw in items.values()]

    def _item(self, event: dict, person_id: str) -> tuple[int, RawItem] | None:
        label = _LABELS.get(event.get("type", ""))
        if label is None:
            return None
        if (
            event["type"] == "CreateEvent"
            and (event.get("payload") or {}).get("ref_type") != "repository"
        ):
            label = _LABELS["PushEvent"]  # a new branch or tag is only activity, not a new repo
        repo = (event.get("repo") or {}).get("name")
        if not repo:
            return None
        text, rank = label
        url = f"https://github.com/{repo}"
        return rank, RawItem(
            id=RawItem.make_id(f"{url}#{person_id}"),
            source=self.name,
            kind="post",
            title=f"{text} {repo}",
            url=url,
            published=datetime.fromisoformat(event["created_at"]),
            extra={"person_id": person_id, "event_type": event["type"]},
        )
