from augurai.domain.catalog import normalize_model_key
from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://huggingface.co/api/models"
LLM_TAGS = {"text-generation", "image-text-to-text", "any-to-any", "text2text-generation"}


class HuggingFaceModelsSource:
    name = "huggingface-models"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        response = ctx.http.get(URL, params={"sort": "trendingScore", "limit": 50})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise SourceError("unexpected payload: not a list")
        items: list[RawItem] = []
        for row in rows:
            if row.get("pipeline_tag") not in LLM_TAGS:
                continue
            model_id = str(row["id"])
            owner = model_id.split("/")[0]
            url = f"https://huggingface.co/{model_id}"
            items.append(
                RawItem(
                    id=RawItem.make_id(url),
                    source=self.name,
                    kind="model",
                    title=model_id,
                    url=url,
                    metrics={"hf_trending": float(row.get("trendingScore", 0))},
                    extra={
                        "model_key": normalize_model_key(owner, model_id),
                        "name": model_id.split("/")[-1],
                        "provider": owner,
                        "open_weights": True,
                        "downloads": row.get("downloads", 0),
                        "likes": row.get("likes", 0),
                        "released": (row.get("createdAt") or "")[:10] or None,
                    },
                )
            )
        return items
