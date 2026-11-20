from augurai.config import Settings
from augurai.sources.artificial_analysis import ArtificialAnalysisSource
from augurai.sources.base import Source
from augurai.sources.huggingface import HuggingFaceModelsSource
from augurai.sources.openrouter import OpenRouterSource


def all_sources(settings: Settings) -> list[Source]:
    return [OpenRouterSource(), HuggingFaceModelsSource(), ArtificialAnalysisSource()]
