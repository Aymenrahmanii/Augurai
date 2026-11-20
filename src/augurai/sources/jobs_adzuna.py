import httpx

from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

BASE = "https://api.adzuna.com/v1/api/jobs"
RESULTS = 20


class AdzunaSource:
    name = "jobs-adzuna"
    required_env: tuple[str, ...] = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY")

    def _search(self, ctx: SourceContext, params: dict) -> dict:
        country = ctx.settings.adzuna_country
        response = ctx.http.get(
            f"{BASE}/{country}/search/1",
            params={
                "app_id": ctx.env["ADZUNA_APP_ID"],
                "app_key": ctx.env["ADZUNA_APP_KEY"],
                "results_per_page": RESULTS,
                **params,
            },
        )
        response.raise_for_status()
        return response.json()

    def _aggregate(self, ctx: SourceContext, keyword: str | None, count: int) -> RawItem:
        label = keyword or "total"
        url = f"https://www.adzuna.fr/search?q={label}"
        return RawItem(
            id=RawItem.make_id(f"adzuna-aggregate:{ctx.settings.adzuna_country}:{label}"),
            source=self.name,
            kind="job",
            title=f"{label} ({count})",
            url=url,
            extra={"market": "fr", "aggregate": True, "keyword": keyword, "count": count},
        )

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        items: list[RawItem] = []
        errors: list[str] = []
        try:
            body = self._search(ctx, {"category": "it-jobs"})
        except httpx.HTTPError as exc:
            errors.append(f"it-jobs: {exc}")
        else:
            items.append(self._aggregate(ctx, None, int(body.get("count", 0))))
            for row in body.get("results", []):
                text = f"{row.get('title', '')} {row.get('description', '')}"
                items.append(
                    RawItem(
                        id=RawItem.make_id(f"adzuna:{row['id']}"),
                        source=self.name,
                        kind="job",
                        title=str(row.get("title", "")).strip(),
                        url=row.get("redirect_url", ""),
                        extra={"market": "fr", "text": text[:2000]},
                    )
                )
        for keyword in ctx.settings.job_keywords:
            try:
                body = self._search(ctx, {"what": keyword, "category": "it-jobs"})
            except httpx.HTTPError as exc:
                errors.append(f"{keyword}: {exc}")
                continue
            items.append(self._aggregate(ctx, keyword, int(body.get("count", 0))))
        if not items:
            raise SourceError("; ".join(errors)[:300])
        return items
