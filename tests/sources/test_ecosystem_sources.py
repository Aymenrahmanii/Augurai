import httpx
import respx

from augurai.sources.base import SourceError
from augurai.sources.github_repos import GitHubReposSource
from augurai.sources.github_skills import GitHubSkillsSource
from augurai.sources.mcp_registry import McpRegistrySource


@respx.mock
def test_github_repos_covers_every_topic(ctx, fixture):
    route = respx.get("https://api.github.com/search/repositories").respond(
        json=fixture("github/search_repos.json")
    )
    items = GitHubReposSource().fetch(ctx)
    assert route.call_count == len(ctx.settings.github_topics)
    assert items and {i.kind for i in items} <= {"repo", "agent"}
    first = items[0]
    assert first.extra["owner"] and first.metrics["stars"] > 0
    # the same repo found under two topics is emitted once
    assert len({i.id for i in items}) == len(items)


@respx.mock
def test_github_repos_tolerates_one_failing_topic(ctx, fixture):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403, json={"message": "rate limited"})
        return httpx.Response(200, json=fixture("github/search_repos.json"))

    respx.get("https://api.github.com/search/repositories").mock(side_effect=handler)
    assert GitHubReposSource().fetch(ctx)


@respx.mock
def test_github_repos_raises_when_every_topic_fails(ctx):
    respx.get("https://api.github.com/search/repositories").respond(403)
    try:
        GitHubReposSource().fetch(ctx)
    except SourceError:
        return
    raise AssertionError("expected SourceError")


@respx.mock
def test_github_repos_sends_token_when_present(ctx, fixture):
    route = respx.get("https://api.github.com/search/repositories").respond(
        json=fixture("github/search_repos.json")
    )
    ctx.env = {"GITHUB_TOKEN": "tok"}
    GitHubReposSource().fetch(ctx)
    assert route.calls.last.request.headers["authorization"] == "Bearer tok"


@respx.mock
def test_github_skills_are_skill_kind(ctx, fixture):
    respx.get("https://api.github.com/search/repositories").respond(
        json=fixture("github/search_skills.json")
    )
    items = GitHubSkillsSource().fetch(ctx)
    assert items and all(i.kind == "skill" for i in items)


@respx.mock
def test_mcp_registry_dedupes_versions(ctx, fixture):
    respx.get("https://registry.modelcontextprotocol.io/v0/servers").respond(
        json=fixture("mcp/servers.json")
    )
    items = McpRegistrySource().fetch(ctx)
    assert items and all(i.kind == "mcp" for i in items)
    names = [i.extra["server_name"] for i in items]
    assert len(names) == len(set(names))
    assert all(i.extra["owner"] for i in items)
