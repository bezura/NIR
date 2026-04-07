from __future__ import annotations

"""Factory helpers that wire the default categorization and tagging services."""

from dataclasses import dataclass

from nir_tagging_service.categorization import (
    EmbeddingCategoryClassifier,
    SentenceTransformerEmbedder,
)
from nir_tagging_service.config import Settings
from nir_tagging_service.embeddings import SharedSentenceTransformerProvider
from nir_tagging_service.llm_enhancement import OpenAICompatibleEnhancer
from nir_tagging_service.tag_extraction import KeyBERTKeywordExtractor, KeywordTagger


@dataclass(frozen=True, slots=True)
class PipelineServices:
    """Container for the service objects used by the processing pipeline."""

    categorizer: object
    tagger: object
    enhancer: object | None = None


def build_default_pipeline_services(settings: Settings) -> PipelineServices:
    """Create the default model-backed services from application settings."""

    embedding_provider = SharedSentenceTransformerProvider(settings.embedding_model_name)
    embedder = SentenceTransformerEmbedder(embedding_provider)
    enhancer = None

    if settings.openai_base_url and settings.openai_api_key and settings.openai_model:
        enhancer = OpenAICompatibleEnhancer(
            api_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            folder_id=settings.openai_project,
            timeout_seconds=settings.openai_timeout_seconds,
        )

    return PipelineServices(
        categorizer=EmbeddingCategoryClassifier(embedder=embedder),
        tagger=KeywordTagger(extractor=KeyBERTKeywordExtractor(embedding_provider)),
        enhancer=enhancer,
    )
