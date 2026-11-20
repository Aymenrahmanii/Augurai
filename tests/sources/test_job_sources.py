import httpx
import pytest
import respx

from augurai.sources.base import SourceError, run_sources
from augurai.sources.jobs_adzuna import AdzunaSource
from augurai.sources.jobs_hn import HnHiringSource
from augurai.sources.jobs_remoteok import RemoteOkSource

SEARCH_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"
SEARCH = "https://hn.algolia.com/api/v1/search"


def top_level(story_id: int, text: str, n: int) -> dict:
    return {
        "objectID": str(1000 + n),
        "parent_id": story_id,
        "story_id": story_id,
        "comment_text": text,
        "created_at": "2026-11-03T10:00:00Z",
    }


@respx.mock
def test_hn_hiring_keeps_only_top_level_postings(ctx, fixture):
    respx.get(SEARCH_BY_DATE).respond(json=fixture("hn/whoishiring.json"))
    hits = [
        top_level(
            50338728, "Acme | ML Engineer | Remote | We use &lt;b&gt;RAG&lt;/b&gt; &amp; agents", 1
        ),
        top_level(50338728, "Beta | Backend | NYC", 2),
        *fixture("hn/hiring_comments.json")["hits"],  # nested replies: parent_id != story id
    ]
    respx.get(SEARCH).respond(json={"hits": hits, "nbPages": 1})
    items = HnHiringSource().fetch(ctx)
    assert len(items) == 2
    assert all(i.kind == "job" and i.extra["market"] == "global" for i in items)
    assert "RAG" in items[0].extra["text"] and "<b>" not in items[0].extra["text"]
    assert items[0].title.startswith("Acme")


@respx.mock
def test_hn_hiring_ignores_non_hiring_threads(ctx):
    respx.get(SEARCH_BY_DATE).respond(
        json={"hits": [{"objectID": "1", "title": "Ask HN: Who wants to be hired? (X)"}]}
    )
    with pytest.raises(SourceError, match="Who is hiring"):
        HnHiringSource().fetch(ctx)


@respx.mock
def test_remoteok_skips_legal_notice(ctx, fixture):
    respx.get("https://remoteok.com/api").respond(json=fixture("remoteok/jobs.json"))
    items = RemoteOkSource().fetch(ctx)
    assert len(items) == len(fixture("remoteok/jobs.json")) - 1
    assert all(i.extra["market"] == "global" and i.extra["text"] for i in items)


@respx.mock
def test_adzuna_aggregates_per_keyword(ctx, fixture):
    route = respx.get(url__regex=r"https://api\.adzuna\.com/v1/api/jobs/fr/search/1.*").respond(
        json=fixture("adzuna/search_fr.json")
    )
    ctx.env = {"ADZUNA_APP_ID": "i", "ADZUNA_APP_KEY": "k"}
    items = AdzunaSource().fetch(ctx)
    aggregates = [i for i in items if i.extra.get("aggregate")]
    assert {i.extra["keyword"] for i in aggregates} == {*ctx.settings.job_keywords, None}
    assert all(i.extra["count"] == 2 and i.extra["market"] == "fr" for i in aggregates)
    postings = [i for i in items if not i.extra.get("aggregate")]
    assert postings and all("text" in i.extra for i in postings)
    assert route.call_count == len(ctx.settings.job_keywords) + 1
    assert route.calls.last.request.url.params["app_id"] == "i"
    assert httpx


def test_adzuna_skipped_without_keys(ctx):
    run = run_sources([AdzunaSource()], ctx, {})
    assert run.skipped == ["jobs-adzuna"]
