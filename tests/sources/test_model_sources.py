import httpx
import respx

from augurai.sources.artificial_analysis import ArtificialAnalysisSource
from augurai.sources.huggingface import HuggingFaceModelsSource
from augurai.sources.openrouter import OpenRouterSource


@respx.mock
def test_openrouter_parses_fixture(ctx, fixture):
    respx.get("https://openrouter.ai/api/v1/models").respond(json=fixture("openrouter/models.json"))
    items = OpenRouterSource().fetch(ctx)
    assert items and all(i.kind == "model" for i in items)
    assert all("price_in" in i.extra and "model_key" in i.extra for i in items)
    assert all(
        ":" not in i.url.removeprefix("https://openrouter.ai/") for i in items
    )  # no ":batch" variants
    pixtral = next(i for i in items if i.extra["model_key"] == "pixtral-large-2502")
    assert pixtral.extra["price_in"] == 2.0 and pixtral.extra["price_out"] == 6.0


@respx.mock
def test_huggingface_marks_open_weights(ctx, fixture):
    respx.get("https://huggingface.co/api/models").respond(json=fixture("huggingface/models.json"))
    items = HuggingFaceModelsSource().fetch(ctx)
    assert items and all(i.extra["open_weights"] is True for i in items)
    assert all("hf_trending" in i.metrics for i in items)


@respx.mock
def test_artificial_analysis_scores(ctx, fixture):
    respx.get("https://artificialanalysis.ai/api/v2/language/models/free").respond(
        json=fixture("aa/models_free.json")
    )
    ctx.env = {"ARTIFICIAL_ANALYSIS_API_KEY": "k"}
    items = ArtificialAnalysisSource().fetch(ctx)
    a = next(i for i in items if i.extra["model_key"] == "synthetic-model-a")
    assert a.metrics["intelligence"] == 72.5 and a.metrics["output_tps"] == 78.0
    assert a.extra["price_in"] == 3.0
    b = next(i for i in items if i.extra["model_key"] == "synthetic-model-b")
    assert "coding" not in b.metrics  # nulls are not zeros
    assert ArtificialAnalysisSource.required_env == ("ARTIFICIAL_ANALYSIS_API_KEY",)


@respx.mock
def test_artificial_analysis_sends_key_header(ctx, fixture):
    route = respx.get("https://artificialanalysis.ai/api/v2/language/models/free").respond(
        json=fixture("aa/models_free.json")
    )
    ctx.env = {"ARTIFICIAL_ANALYSIS_API_KEY": "k"}
    ArtificialAnalysisSource().fetch(ctx)
    assert route.calls.last.request.headers["x-api-key"] == "k"
    assert httpx  # keep import used
