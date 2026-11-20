from augurai.domain.catalog import normalize_model_key
from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://artificialanalysis.ai/api/v2/language/models/free"
MAX_PAGES = 5


class ArtificialAnalysisSource:
    name = "artificial-analysis"
    required_env: tuple[str, ...] = ("ARTIFICIAL_ANALYSIS_API_KEY",)

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        headers = {"x-api-key": ctx.env["ARTIFICIAL_ANALYSIS_API_KEY"]}
        items: list[RawItem] = []
        for page in range(1, MAX_PAGES + 1):
            params = {"page": page} if page > 1 else None
            response = ctx.http.get(URL, headers=headers, params=params)
            response.raise_for_status()
            body = response.json()
            rows = body.get("data")
            if not isinstance(rows, list):
                raise SourceError("unexpected payload: no data list")
            items.extend(self._item(row) for row in rows)
            if not (body.get("pagination") or {}).get("has_more"):
                break
        return items

    def _item(self, row: dict) -> RawItem:
        evals = row.get("evaluations") or {}
        # Keep every index the API returns (nulls mean "not measured", never zero), so new
        # benchmarks show up without a code change.
        metrics = {
            key.removeprefix("artificial_analysis_").removesuffix("_index"): float(value)
            for key, value in evals.items()
            if key.endswith("_index") and isinstance(value, int | float)
        }
        tps = (row.get("performance_v3") or {}).get("mean_output_tokens_per_second")
        if tps is not None:
            metrics["output_tps"] = float(tps)
        creator = (row.get("model_creator") or {}).get("name") or "unknown"
        pricing = row.get("pricing") or {}
        url = f"https://artificialanalysis.ai/models/{row['slug']}"
        return RawItem(
            id=RawItem.make_id(url),
            source=self.name,
            kind="model",
            title=str(row["name"]),
            url=url,
            metrics=metrics,
            extra={
                "model_key": normalize_model_key(creator, row["slug"]),
                "name": row["name"],
                "provider": creator,
                "price_in": pricing.get("price_1m_input_tokens"),
                "price_out": pricing.get("price_1m_output_tokens"),
                "released": row.get("release_date"),
            },
        )
