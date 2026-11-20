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


def test_best_at_covers_the_domain_indices():
    scores = {
        "artificial-analysis": {
            "engineering": 70.0,
            "finance_and_accounting": 60.0,
            "legal": 50.0,
            "healthcare_and_medical": 40.0,
            "strategy_and_ops": 30.0,
            "economics": 20.0,
        }
    }
    best = compute_best_at({"a": model("a", scores=scores), "b": model("b")}, top_n=1)
    assert set(best["a"].best_at) == {
        "engineering",
        "finance",
        "legal",
        "healthcare",
        "strategy",
        "economics",
    }
    assert best["b"].best_at == []


def test_family_key_ignores_provider_prefix_and_variant_suffix():
    from augurai.domain.catalog import family_key

    names = [
        "Anthropic: Claude Fable 5.2",
        "Claude Fable 5.2 (Xhigh, Default Fallback)",
        "Claude Fable 5.2 (High)",
        "claude fable 5.2",
    ]
    assert len({family_key(n) for n in names}) == 1
    assert family_key("Claude Fable 5.2") != family_key("Claude Fable 5.1")
    assert family_key("Mistral: Pixtral Large 2502") == family_key("Pixtral Large 2502")
    assert family_key("(Beta)") == "(beta)"  # never collapses to an empty key


def named(mid: str, name: str, **kw) -> Model:
    return Model(id=mid, name=name, provider="p", first_seen=TODAY, **kw)


def test_best_at_counts_one_variant_per_family():
    def intel(v):
        return {"artificial-analysis": {"intelligence": v, "legal": v}}

    models = {
        "a1": named("a1", "Alpha 1", scores=intel(90.0)),
        "a2": named("a2", "Alpha 1 (High)", scores=intel(89.0)),
        "a3": named("a3", "Alpha 1 (Xhigh)", scores=intel(88.0)),
        "b": named("b", "Beta 2", scores=intel(70.0)),
        "c": named("c", "Gamma 3", scores=intel(60.0)),
        "d": named("d", "Delta 4", scores=intel(50.0)),
    }
    best = compute_best_at(models, top_n=3)
    winners = {k for k, m in best.items() if "legal" in m.best_at}
    assert winners == {"a1", "b", "c"}  # the best Alpha variant, then two other families
