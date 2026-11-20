from datetime import date

from augurai.domain.catalog import compute_best_at, merge_models, normalize_model_key
from augurai.models import Model, RawItem

TODAY = date(2026, 11, 20)


def raw(source: str, key: str, metrics=None, **extra) -> RawItem:
    return RawItem(
        id=f"{source}-{key}",
        source=source,
        kind="model",
        title=key,
        url=f"https://x/{source}/{key}",
        metrics=metrics or {},
        extra={"model_key": key, "provider": "p", **extra},
    )


def model(mid: str, **kwargs) -> Model:
    return Model(id=mid, name=mid, provider="p", first_seen=TODAY, **kwargs)


def test_normalize_model_key():
    assert normalize_model_key("anthropic", "anthropic/claude-opus-5.5") == "claude-opus-5-5"
    assert normalize_model_key("openai", "gpt-5-20260101") == "gpt-5"
    assert normalize_model_key("x", "Some Model v2") == "some-model-v2"


def test_merge_keeps_models_missing_from_new_items():
    existing = {"m1": model("m1")}
    assert "m1" in merge_models(existing, [], TODAY)


def test_merge_combines_sources_by_key():
    items = [
        raw("openrouter", "opus", price_in=5.0, price_out=25.0, context_window=1000000),
        raw("artificial-analysis", "opus", metrics={"coding": 70.0}),
    ]
    m = merge_models({}, items, TODAY)["opus"]
    assert m.price_in == 5.0 and m.context_window == 1000000
    assert m.scores["artificial-analysis"]["coding"] == 70.0
    assert m.first_seen == TODAY


def test_merge_replaces_source_scores_whole_and_keeps_missing_fields():
    existing = {
        "opus": model(
            "opus", price_in=5.0, scores={"artificial-analysis": {"coding": 1.0, "agentic": 2.0}}
        )
    }
    out = merge_models(
        existing, [raw("artificial-analysis", "opus", metrics={"coding": 9.0})], TODAY
    )
    assert out["opus"].scores["artificial-analysis"] == {"coding": 9.0}
    assert out["opus"].price_in == 5.0


def test_best_at_top_n():
    models = {
        f"m{i}": model(f"m{i}", scores={"artificial-analysis": {"coding": float(i)}})
        for i in range(5)
    }
    out = compute_best_at(models, top_n=3)
    assert {k for k, m in out.items() if "coding" in m.best_at} == {"m4", "m3", "m2"}


def test_best_at_skips_categories_without_data():
    out = compute_best_at({"a": model("a")}, top_n=3)
    assert out["a"].best_at == []


def test_best_at_cost_efficiency_and_open_weights():
    cheap = model(
        "cheap", price_in=0.1, price_out=0.4, scores={"artificial-analysis": {"intelligence": 50.0}}
    )
    pricey = model(
        "pricey",
        price_in=10.0,
        price_out=40.0,
        open_weights=True,
        scores={"artificial-analysis": {"intelligence": 60.0}},
    )
    out = compute_best_at({"cheap": cheap, "pricey": pricey}, top_n=1)
    assert (
        "cost_efficiency" in out["cheap"].best_at and "cost_efficiency" not in out["pricey"].best_at
    )
    assert "open_weights" in out["pricey"].best_at
