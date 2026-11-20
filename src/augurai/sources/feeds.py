import re
from calendar import timegm
from datetime import UTC, datetime

import feedparser
import httpx

from augurai.models import Person, RawItem
from augurai.sources.base import SourceContext, SourceError

ENTRIES_PER_FEED = 10
_GITHUB_LOGIN = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})(?=[/\"'\s<)&?#]|$)")
_NOT_LOGINS = {
    "orgs", "topics", "features", "sponsors", "settings", "login", "marketplace", "about",
    "pricing", "enterprise", "collections", "trending", "explore", "apps", "notifications",
    "pulls", "issues", "search", "readme", "security", "customer-stories", "resources",
}  # fmt: skip


def linked_logins(text: str) -> list[str]:
    found = {m for m in _GITHUB_LOGIN.findall(text) if m.lower() not in _NOT_LOGINS}
    return sorted(found)


def _entry_text(entry: feedparser.FeedParserDict) -> str:
    parts = [entry.get("summary", "")]
    parts.extend(c.get("value", "") for c in entry.get("content", []))
    return " ".join(parts)


class FeedsSource:
    name = "feeds"
    required_env: tuple[str, ...] = ()

    def __init__(self, extra_people: list[Person] | None = None) -> None:
        self.extra_people = extra_people or []

    def _feeds(self, ctx: SourceContext) -> dict[str, str | None]:
        feeds: dict[str, str | None] = {url: None for url in ctx.settings.feeds}
        links = [(p.id, p.links) for p in ctx.settings.seed_people]
        links += [(p.id, p.links) for p in self.extra_people]
        for person_id, person_links in links:
            for key in ("rss", "youtube"):
                if url := person_links.get(key):
                    feeds[url] = person_id
        return feeds

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        items: dict[str, RawItem] = {}
        errors: list[str] = []
        # Person-owned feeds first, so an entry seen in both a general and a personal feed is attributed.
        ordered = sorted(self._feeds(ctx).items(), key=lambda pair: pair[1] is None)
        for feed_url, person_id in ordered:
            try:
                response = ctx.http.get(feed_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                errors.append(f"{feed_url}: {exc}")
                continue
            parsed = feedparser.parse(response.content)
            if not parsed.entries:
                errors.append(f"{feed_url}: no entries")
                continue
            kind = "video" if "youtube.com/feeds" in feed_url else "post"
            for entry in parsed.entries[:ENTRIES_PER_FEED]:
                link = entry.get("link")
                if not link:
                    continue
                stamp = entry.get("published_parsed") or entry.get("updated_parsed")
                extra: dict[str, object] = {
                    "feed": feed_url,
                    "linked_people": linked_logins(_entry_text(entry)),
                }
                if person_id:
                    extra["person_id"] = person_id
                items.setdefault(
                    link,
                    RawItem(
                        id=RawItem.make_id(link),
                        source=self.name,
                        kind=kind,
                        title=entry.get("title", ""),
                        url=link,
                        author=entry.get("author"),
                        published=datetime.fromtimestamp(timegm(stamp), UTC) if stamp else None,
                        extra=extra,
                    ),
                )
        if not items:
            raise SourceError("; ".join(errors)[:300] or "no feed entries")
        return list(items.values())
