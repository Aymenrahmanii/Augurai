"""Merge model items from all sources into the catalog and compute best-at categories."""

import re
from collections import defaultdict
from collections.abc import Callable
from datetime import date

from augurai.models import Category, Model, RawItem

_DATE_SUFFIX = re.compile(r"-\d{8}$")
_PROVIDER_PREFIX = re.compile(r"^[^:()]{1,40}:\s*")
_VARIANT_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")


def normalize_model_key(provider: str, name: str) -> str:
    key = name.lower().split("/")[-1]
    key = _DATE_SUFFIX.sub("", key)
    return re.sub(r"[\s.]+", "-", key).strip("-")


def _released(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _apply(model: Model, item: RawItem) -> Model:
    extra = item.extra
    update: dict[str, object] = {}
    if provider := extra.get("provider"):
        update["provider"] = provider
    if (released := _released(extra.get("released"))) is not None:
        update["released"] = released
    if extra.get("open_weights"):
        update["open_weights"] = True
    for field in ("context_window", "price_in", "price_out"):
        if extra.get(field) is not None:
            update[field] = extra[field]
    if extra.get("modalities"):
        update["modalities"] = list(extra["modalities"])
    scores = dict(model.scores)
    if item.metrics:
        scores[item.source] = dict(item.metrics)
    update["scores"] = scores
    update["links"] = {**model.links, item.source: item.url}
    return model.model_copy(update=update)


def merge_models(existing: dict[str, Model], items: list[RawItem], today: date) -> dict[str, Model]:
    merged = dict(existing)
    grouped: dict[str, list[RawItem]] = defaultdict(list)
    for item in items:
        if key := item.extra.get("model_key"):
            grouped[key].append(item)
    for key, group in grouped.items():
        model = merged.get(key) or Model(
            id=key,
            name=str(group[0].extra.get("name") or group[0].title),
            provider=str(group[0].extra.get("provider", "unknown")),
            first_seen=today,
        )
        for item in group:
            model = _apply(model, item)
        merged[key] = model
    return merged


def _score(model: Model, key: str) -> float | None:
    for scores in model.scores.values():
        if key in scores:
            return scores[key]
    return None


def _blended_price(model: Model) -> float | None:
    if model.price_in is None or model.price_out is None:
        return None
    price = (3 * model.price_in + model.price_out) / 4
    return price if price > 0 else None


def _cost_efficiency(model: Model) -> float | None:
    intelligence, price = _score(model, "intelligence"), _blended_price(model)
    if intelligence is None or price is None:
        return None
    return intelligence / price


def _multimodal(model: Model) -> float | None:
    extra = len([m for m in model.modalities if m != "text"])
    return float(extra) if extra else None


def _open_weights(model: Model) -> float | None:
    return _score(model, "intelligence") if model.open_weights else None


_METRICS: dict[Category, Callable[[Model], float | None]] = {
    "coding": lambda m: _score(m, "coding"),
    "agentic": lambda m: _score(m, "agentic"),
    "reasoning": lambda m: _score(m, "reasoning"),
    "long_context": lambda m: float(m.context_window) if m.context_window else None,
    "multimodal": _multimodal,
    "speed": lambda m: _score(m, "output_tps"),
    "cost_efficiency": _cost_efficiency,
    "open_weights": _open_weights,
    # Artificial Analysis domain indices: how well a model does professional tasks in a field.
    "engineering": lambda m: _score(m, "engineering"),
    "finance": lambda m: _score(m, "finance_and_accounting"),
    "legal": lambda m: _score(m, "legal"),
    "healthcare": lambda m: _score(m, "healthcare_and_medical"),
    "strategy": lambda m: _score(m, "strategy_and_ops"),
    "economics": lambda m: _score(m, "economics"),
}


def family_key(name: str) -> str:
    """A model's family: its name without the provider prefix and "(High)"-style variant suffixes."""
    base = _PROVIDER_PREFIX.sub("", name.strip())
    while (stripped := _VARIANT_SUFFIX.sub("", base)) != base and stripped:
        base = stripped
    return re.sub(r"\s+", " ", base).strip().lower()


def compute_best_at(models: dict[str, Model], top_n: int = 3) -> dict[str, Model]:
    best: dict[str, list[Category]] = {key: [] for key in models}
    for category, metric in _METRICS.items():
        ranked = [(value, key) for key, m in models.items() if (value := metric(m)) is not None]
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        families: set[str] = set()
        for _, key in ranked:  # best variant first; each family can win a category only once
            family = family_key(models[key].name)
            if family in families:
                continue
            families.add(family)
            best[key].append(category)
            if len(families) == top_n:
                break
    return {key: m.model_copy(update={"best_at": best[key]}) for key, m in models.items()}
