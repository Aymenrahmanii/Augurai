import httpx
import pytest
import respx

from augurai.models import Person
from augurai.sources.base import SourceError
from augurai.sources.feeds import FeedsSource
from augurai.sources.github_people import GitHubPeopleSource
from augurai.sources.hackernews import HackerNewsSource
from augurai.sources.hf_papers import HfPapersSource

SIMON_FEED = "https://simonwillison.net/atom/everything/"
LATENT_FEED = "https://www.latent.space/feed"

ATOM_WITH_LINK = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>t</title>
<entry><title>Post</title><link href="https://example.com/p"/><id>1</id>
<updated>2026-11-19T10:00:00Z</updated>
<content type="html">&lt;a href="https://github.com/newdev/cool"&gt;x&lt;/a&gt;
&lt;a href="https://github.com/orgs/foo"&gt;y&lt;/a&gt;</content></entry></feed>"""


@respx.mock
def test_hackernews_filters_by_points_and_dedupes(ctx, fixture):
    respx.get("https://hn.algolia.com/api/v1/search_by_date").respond(
        json=fixture("hn/stories.json")
    )
    items = HackerNewsSource().fetch(ctx)
    assert items and all(i.kind == "hn" for i in items)
    assert all(i.metrics["points"] >= ctx.settings.hn_min_points for i in items)
    assert len({i.id for i in items}) == len(items)


@respx.mock
def test_hackernews_drops_low_point_stories(ctx):
    hits = [
        {"objectID": "1", "title": "big", "url": "https://a.dev", "points": 500, "author": "u",
         "num_comments": 3, "created_at": "2026-11-19T10:00:00Z"},
        {"objectID": "2", "title": "small", "url": "https://b.dev", "points": 10, "author": "u",
         "num_comments": 0, "created_at": "2026-11-19T10:00:00Z"},
    ]  # fmt: skip
    respx.get("https://hn.algolia.com/api/v1/search_by_date").respond(json={"hits": hits})
    assert [i.title for i in HackerNewsSource().fetch(ctx)] == ["big"]


@respx.mock
def test_feeds_set_person_id_only_for_known_people(ctx, fixture):
    atom = fixture("feeds/simonwillison.atom")

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == SIMON_FEED:
            return httpx.Response(200, text=atom)
        if str(request.url) == LATENT_FEED:
            return httpx.Response(200, text=ATOM_WITH_LINK)
        return httpx.Response(404)

    respx.route(method="GET").mock(side_effect=handler)
    items = FeedsSource().fetch(ctx)
    simon = [i for i in items if i.extra.get("feed") == SIMON_FEED]
    latent = [i for i in items if i.extra.get("feed") == LATENT_FEED]
    assert simon and all(i.extra["person_id"] == "simon-willison" for i in simon)
    assert latent and all("person_id" not in i.extra for i in latent)


@respx.mock
def test_feeds_extract_linked_github_logins(ctx):
    respx.route(method="GET").mock(
        side_effect=lambda r: (
            httpx.Response(200, text=ATOM_WITH_LINK)
            if str(r.url) == LATENT_FEED
            else httpx.Response(404)
        )
    )
    items = FeedsSource().fetch(ctx)
    assert items[0].extra["linked_people"] == ["newdev"]


@respx.mock
def test_feeds_skip_malformed_feed_but_keep_others(ctx, fixture):
    atom = fixture("feeds/simonwillison.atom")
    respx.route(method="GET").mock(
        side_effect=lambda r: (
            httpx.Response(200, text=atom)
            if str(r.url) == SIMON_FEED
            else httpx.Response(200, text="<html>not a feed</html>")
        )
    )
    assert FeedsSource().fetch(ctx)


@respx.mock
def test_feeds_raise_when_every_feed_fails(ctx):
    respx.route(method="GET").respond(500)
    with pytest.raises(SourceError):
        FeedsSource().fetch(ctx)


@respx.mock
def test_feeds_include_extra_people(ctx, fixture):
    atom = fixture("feeds/simonwillison.atom")
    extra = Person(
        id="newdev", name="newdev", status="followed", links={"rss": "https://newdev.dev/feed"}
    )
    respx.route(method="GET").mock(
        side_effect=lambda r: (
            httpx.Response(200, text=atom)
            if str(r.url) == "https://newdev.dev/feed"
            else httpx.Response(404)
        )
    )
    items = FeedsSource(extra_people=[extra]).fetch(ctx)
    assert items and all(i.extra["person_id"] == "newdev" for i in items)


@respx.mock
def test_hf_papers_fixture(ctx, fixture):
    respx.get("https://huggingface.co/api/daily_papers").respond(
        json=fixture("hfpapers/daily.json")
    )
    items = HfPapersSource().fetch(ctx)
    assert items and all(i.kind == "paper" and "upvotes" in i.metrics for i in items)


@respx.mock
def test_github_people_emits_activity_per_repo(ctx, fixture):
    events = fixture("github/events_mattpocock.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/mattpocock/events/public":
            return httpx.Response(200, json=events)
        return httpx.Response(404)

    respx.route(method="GET").mock(side_effect=handler)
    items = GitHubPeopleSource().fetch(ctx)
    assert items and all(i.extra["person_id"] == "matt-pocock" for i in items)
    urls = [i.url for i in items]
    assert len(urls) == len(set(urls))  # one item per person and repo
    assert all(i.published is not None for i in items)
