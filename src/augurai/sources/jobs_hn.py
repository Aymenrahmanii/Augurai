import html
import re
from datetime import datetime

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

SEARCH_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"
SEARCH = "https://hn.algolia.com/api/v1/search"
MAX_PAGES = 5
TAG = re.compile(r"<[^>]+>")


def clean(comment_html: str) -> str:
    text = TAG.sub(" ", html.unescape(comment_html.replace("<p>", "\n")))
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


class HnHiringSource:
    name = "jobs-hn"
    required_env: tuple[str, ...] = ()

    def _thread_id(self, ctx: SourceContext) -> int:
        response = ctx.http.get(
            SEARCH_BY_DATE,
            params={"tags": "story,author_whoishiring", "hitsPerPage": 5},
        )
        response.raise_for_status()
        for hit in response.json().get("hits", []):
            if str(hit.get("title", "")).startswith("Ask HN: Who is hiring?"):
                return int(hit["objectID"])
        raise SourceError("no 'Who is hiring' thread found")

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        story_id = self._thread_id(ctx)
        items: list[RawItem] = []
        for page in range(MAX_PAGES):
            response = ctx.http.get(
                SEARCH,
                params={
                    "tags": f"comment,story_{story_id}",
                    "hitsPerPage": 1000,
                    "page": page,
                },
            )
            response.raise_for_status()
            body = response.json()
            for hit in body.get("hits", []):
                if hit.get("parent_id") != story_id:  # replies are not postings
                    continue
                text = clean(hit.get("comment_text") or "")
                if not text:
                    continue
                url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
                items.append(
                    RawItem(
                        id=RawItem.make_id(url),
                        source=self.name,
                        kind="job",
                        title=text.split("\n")[0][:120],
                        url=url,
                        published=datetime.fromisoformat(hit["created_at"]),
                        extra={"market": "global", "text": text[:2000]},
                    )
                )
            if page + 1 >= int(body.get("nbPages", 1)):
                break
        return items
