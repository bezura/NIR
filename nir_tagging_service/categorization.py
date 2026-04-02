from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, Sequence

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nir_tagging_service.category_catalog import (
    DEFAULT_CATEGORIES,
    CategoryDefinition,
)
from nir_tagging_service.embeddings import SentenceTransformerProvider


AGGREGATED_MEAN_WEIGHT = 0.75
AGGREGATED_MAX_WEIGHT = 0.25
LOW_CONFIDENCE_SCORE_THRESHOLD = 0.65
LOW_CONFIDENCE_GAP_THRESHOLD = 0.08
INFORMATIVE_CHUNK_WEIGHT_THRESHOLD = 1.3

TOKEN_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_-]{3,}")
SECTION_MARKERS = (
    "abstract",
    "introduction",
    "overview",
    "background",
    "implementation",
    "architecture",
    "results",
    "discussion",
    "summary",
    "conclusion",
    "заключение",
    "выводы",
    "итоги",
    "введение",
    "обзор",
    "архитектура",
    "результаты",
    "обсуждение",
)


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
    top_1_score: float | None = None
    top_2_score: float | None = None
    confidence_gap: float | None = None
    low_confidence: bool = False
    low_confidence_reasons: list[str] = field(default_factory=list)
    num_chunks_scored: int = 0
    informative_chunk_indices: list[int] = field(default_factory=list)

    def top_k(self, limit: int) -> list[dict[str, float | str]]:
        ranked = sorted(self.similarities.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [{"code": code, "score": float(score)} for code, score in ranked]

    @property
    def effective_top_1_score(self) -> float:
        if self.top_1_score is not None:
            return float(self.top_1_score)
        return float(self.score)

    @property
    def effective_top_2_score(self) -> float:
        if self.top_2_score is not None:
            return float(self.top_2_score)
        ranked = sorted(self.similarities.values(), reverse=True)
        if len(ranked) > 1:
            return float(ranked[1])
        return 0.0

    @property
    def effective_confidence_gap(self) -> float:
        if self.confidence_gap is not None:
            return float(self.confidence_gap)
        return max(0.0, self.effective_top_1_score - self.effective_top_2_score)


def _term_density(text: str) -> float:
    all_tokens = [token.casefold() for token in TOKEN_PATTERN.findall(text)]
    if not all_tokens:
        return 0.0
    dense_tokens = [
        token for token in all_tokens
        if len(token) >= 7 or "-" in token or "_" in token
    ]
    if not dense_tokens:
        return 0.0
    return len(set(dense_tokens)) / len(all_tokens)


def compute_chunk_weight(chunk: str, index: int, total_chunks: int) -> tuple[float, bool]:
    weight = 1.0
    lowered = chunk.casefold()
    density = _term_density(chunk)

    if total_chunks > 1 and index == 0:
        weight += 0.2
    if total_chunks > 1 and index == total_chunks - 1:
        weight += 0.35
    if any(marker in lowered for marker in SECTION_MARKERS):
        weight += 0.35
    if density >= 0.6:
        weight += 0.5
    elif density >= 0.45:
        weight += 0.25

    informative = weight >= INFORMATIVE_CHUNK_WEIGHT_THRESHOLD
    return round(weight, 3), informative


def aggregate_similarity_rows(similarities: np.ndarray, weights: Sequence[float]) -> np.ndarray:
    similarity_matrix = np.asarray(similarities, dtype=float)
    if similarity_matrix.ndim != 2 or similarity_matrix.shape[0] == 0:
        raise ValueError("aggregate_similarity_rows() requires a non-empty 2D similarity matrix")

    if len(weights) != similarity_matrix.shape[0]:
        raise ValueError("weights count must match the number of chunk rows")

    weight_array = np.asarray(weights, dtype=float)
    weight_sum = float(weight_array.sum())
    if weight_sum <= 0:
        raise ValueError("weights must sum to a positive value")

    normalized_weights = weight_array / weight_sum
    weighted_mean = np.sum(similarity_matrix * normalized_weights[:, None], axis=0)
    max_scores = np.max(similarity_matrix, axis=0)
    aggregated = (
        weighted_mean * AGGREGATED_MEAN_WEIGHT
        + max_scores * AGGREGATED_MAX_WEIGHT
    )
    return np.clip(aggregated, 0.0, 1.0)


def _normalize_embedding(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


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
            category_vectors: list[np.ndarray] = []

            for category in self.categories:
                embedding_inputs = list(category.embedding_texts())
                embeddings = self.embedder.encode(embedding_inputs)
                category_vectors.append(
                    _normalize_embedding(np.mean(embeddings, axis=0))
                )

            self._category_embeddings = np.vstack(category_vectors)

        return self._category_embeddings

    def categorize(self, chunks: Sequence[str]) -> CategorizationResult:
        if not chunks:
            raise ValueError("categorize() requires at least one chunk")

        chunk_texts = list(chunks)
        document_embeddings = self.embedder.encode(chunk_texts)
        similarity_matrix = cosine_similarity(document_embeddings, self.category_embeddings)

        chunk_weights: list[float] = []
        informative_chunk_indices: list[int] = []
        for index, chunk in enumerate(chunk_texts):
            weight, informative = compute_chunk_weight(chunk, index=index, total_chunks=len(chunk_texts))
            chunk_weights.append(weight)
            if informative:
                informative_chunk_indices.append(index)

        similarities = aggregate_similarity_rows(similarity_matrix, chunk_weights)
        best_index = int(np.argmax(similarities))
        best_similarity = float(similarities[best_index])
        ranked_scores = sorted((float(score) for score in similarities), reverse=True)
        top_1_score = ranked_scores[0]
        top_2_score = ranked_scores[1] if len(ranked_scores) > 1 else 0.0
        confidence_gap = max(0.0, top_1_score - top_2_score)

        similarity_map = {
            category.code: float(score)
            for category, score in zip(self.categories, similarities)
        }

        low_confidence_reasons: list[str] = []
        if top_1_score < LOW_CONFIDENCE_SCORE_THRESHOLD:
            low_confidence_reasons.append("low_top_score")
        if confidence_gap < LOW_CONFIDENCE_GAP_THRESHOLD:
            low_confidence_reasons.append("small_gap")
        if top_1_score < LOW_CONFIDENCE_SCORE_THRESHOLD or confidence_gap < LOW_CONFIDENCE_GAP_THRESHOLD:
            low_confidence_reasons.append("taxonomy_gap")

        return CategorizationResult(
            category=self.categories[best_index],
            score=max(0.0, min(1.0, best_similarity)),
            similarities=similarity_map,
            top_1_score=top_1_score,
            top_2_score=top_2_score,
            confidence_gap=confidence_gap,
            low_confidence=bool(low_confidence_reasons),
            low_confidence_reasons=low_confidence_reasons,
            num_chunks_scored=len(chunk_texts),
            informative_chunk_indices=informative_chunk_indices,
        )
