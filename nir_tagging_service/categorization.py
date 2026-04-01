from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nir_tagging_service.category_catalog import (
    DEFAULT_CATEGORIES,
    CategoryDefinition,
)
from nir_tagging_service.embeddings import SentenceTransformerProvider


class EmbeddingBackend(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, provider: SentenceTransformerProvider) -> None:
        self.provider = provider

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self.provider.get_model()
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=float)


@dataclass(frozen=True, slots=True)
class CategorizationResult:
    category: CategoryDefinition
    score: float
    similarities: dict[str, float]

    def top_k(self, limit: int) -> list[dict[str, float | str]]:
        ranked = sorted(self.similarities.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [{"code": code, "score": float(score)} for code, score in ranked]


class EmbeddingCategoryClassifier:
    def __init__(
        self,
        embedder: EmbeddingBackend,
        categories: Sequence[CategoryDefinition] | None = None,
    ) -> None:
        self.embedder = embedder
        self.categories = list(categories or DEFAULT_CATEGORIES)
        self._category_embeddings: np.ndarray | None = None

    @property
    def category_embeddings(self) -> np.ndarray:
        if self._category_embeddings is None:
            descriptions = [category.description for category in self.categories]
            self._category_embeddings = self.embedder.encode(descriptions)

        return self._category_embeddings

    def categorize(self, chunks: Sequence[str]) -> CategorizationResult:
        if not chunks:
            raise ValueError("categorize() requires at least one chunk")

        document_embeddings = self.embedder.encode(list(chunks))
        document_embedding = np.mean(document_embeddings, axis=0, keepdims=True)
        similarities = cosine_similarity(document_embedding, self.category_embeddings)[0]
        best_index = int(np.argmax(similarities))
        best_similarity = float(similarities[best_index])

        similarity_map = {
            category.code: float(score)
            for category, score in zip(self.categories, similarities)
        }

        return CategorizationResult(
            category=self.categories[best_index],
            score=max(0.0, min(1.0, best_similarity)),
            similarities=similarity_map,
        )
