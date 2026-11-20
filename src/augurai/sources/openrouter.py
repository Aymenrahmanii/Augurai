from datetime import UTC, datetime

from augurai.domain.catalog import normalize_model_key
from augurai.models import RawItem
from augurai.sources.base import SourceContext, SourceError

URL = "https://openrouter.ai/api/v1/models"


def _per_million(value: object) -> float | None:
    try:
        price = float(value) * 1_000_000  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return round(price, 6) if price >= 0 else None


class OpenRouterSource:
    name = "openrouter"
    required_env: tuple[str, ...] = ()

    def fetch(self, ctx: SourceContext) -> list[RawItem]:
        response = ctx.http.get(URL)
        response.raise_for_status()
        rows = response.json().get("data")
        if not isinstance(rows, list):
            raise SourceError("unexpected payload: no data list")
        items: list[RawItem] = []
        for row in rows:
            model_id = str(row.get("id", ""))
            if not model_id or ":" in model_id:  # skip variants such as ":free" or ":batch"
                continue
            provider = model_id.split("/")[0]
            url = f"https://openrouter.ai/{model_id}"
            created = row.get("created")
            released = (
                datetime.fromtimestamp(created, UTC).date().isoformat()
                if isinstance(created, int | float)
                else None
            )
            pricing = row.get("pricing") or {}
            items.append(
                RawItem(
                    id=RawItem.make_id(url),
                    source=self.name,
                    kind="model",
                    title=str(row.get("name") or model_id),
                    url=url,
                    extra={
                        "model_key": normalize_model_key(provider, model_id),
                        "name": row.get("name") or model_id,
                        "provider": provider,
                        "context_window": row.get("context_length"),
                        "price_in": _per_million(pricing.get("prompt")),
                        "price_out": _per_million(pricing.get("completion")),
                        "modalities": (row.get("architecture") or {}).get("input_modalities", []),
                        "released": released,
                    },
                )
            )
        return items
