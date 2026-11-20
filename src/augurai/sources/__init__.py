from augurai.config import Settings
from augurai.sources.artificial_analysis import ArtificialAnalysisSource
from augurai.sources.base import Source
from augurai.sources.feeds import FeedsSource
from augurai.sources.github_people import GitHubPeopleSource
from augurai.sources.github_repos import GitHubReposSource
from augurai.sources.github_skills import GitHubSkillsSource
from augurai.sources.hackernews import HackerNewsSource
from augurai.sources.hf_papers import HfPapersSource
from augurai.sources.huggingface import HuggingFaceModelsSource
from augurai.sources.mcp_registry import McpRegistrySource
from augurai.sources.openrouter import OpenRouterSource


def all_sources(settings: Settings) -> list[Source]:
    return [
        OpenRouterSource(),
        HuggingFaceModelsSource(),
        ArtificialAnalysisSource(),
        GitHubReposSource(),
        GitHubSkillsSource(),
        McpRegistrySource(),
        HackerNewsSource(),
        FeedsSource(),
        HfPapersSource(),
        GitHubPeopleSource(),
    ]
