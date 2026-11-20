from datetime import datetime

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://huggingface.co/api/daily_papers"


class HfPapersSource:
    name = "hf-papers"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        response = ctx.http.get(URL)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise SourceError("unexpected payload: not a list")
        items: list[RawItem] = []
        for row in rows:
            paper = row.get("paper") or {}
            if not paper.get("id"):
                continue
            url = f"https://huggingface.co/papers/{paper['id']}"
            published = row.get("publishedAt")
            items.append(
                RawItem(
                    id=RawItem.make_id(url),
                    source=self.name,
                    kind="paper",
                    title=paper.get("title") or row.get("title") or "",
                    url=url,
                    published=datetime.fromisoformat(published) if published else None,
                    metrics={"upvotes": float(paper.get("upvotes") or 0)},
                    extra={"summary": (row.get("summary") or "")[:300]},
                )
            )
        return items
