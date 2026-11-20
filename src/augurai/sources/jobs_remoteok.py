from datetime import datetime

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError
from augurai.sources.jobs_hn import clean

URL = "https://remoteok.com/api"


class RemoteOkSource:
    name = "jobs-remoteok"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        response = ctx.http.get(URL)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise SourceError("unexpected payload: not a list")
        items: list[RawItem] = []
        for row in rows[1:]:  # the first element is a legal notice, not a job
            if not isinstance(row, dict) or not row.get("position"):
                continue
            url = row.get("url") or row.get("apply_url") or f"https://remoteok.com/{row['id']}"
            text = f"{row['position']} {row.get('tags', '')} {clean(row.get('description') or '')}"
            stamp = row.get("date")
            items.append(
                RawItem(
                    id=RawItem.make_id(f"remoteok:{row['id']}"),
                    source=self.name,
                    kind="job",
                    title=str(row["position"]),
                    url=url,
                    published=datetime.fromisoformat(stamp) if stamp else None,
                    extra={"market": "global", "text": text[:2000], "company": row.get("company")},
                )
            )
        return items
