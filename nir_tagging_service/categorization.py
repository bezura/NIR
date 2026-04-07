from __future__ import annotations

"""Embedding-based category scoring and confidence estimation."""

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from nir_tagging_service.category_catalog import (
    DEFAULT_CATEGORIES,
    CategoryDefinition,
    iter_categories,
    iter_leaf_categories,
)
from nir_tagging_service.embeddings import SentenceTransformerProvider


AGGREGATED_MEAN_WEIGHT = 0.75
AGGREGATED_MAX_WEIGHT = 0.25
LOW_CONFIDENCE_SCORE_THRESHOLD = 0.65
LOW_CONFIDENCE_GAP_THRESHOLD = 0.08
LONG_DOCUMENT_SCORE_THRESHOLD = 0.58
LONG_DOCUMENT_GAP_THRESHOLD = 0.04
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
    """Protocol implemented by embedding backends usable by the classifier."""

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Adapter around a shared sentence-transformer provider."""

    def __init__(self, provider: SentenceTransformerProvider) -> None:
        self.provider = provider

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode text chunks into normalized NumPy embeddings."""

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
    """Categorization output enriched with confidence and trace diagnostics."""

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
    category_path: list[CategoryDefinition] = field(default_factory=list)
    category_depth: int = 0
    category_is_leaf: bool = True
    classification_trace: list[dict[str, Any]] = field(default_factory=list)

    def top_k(self, limit: int) -> list[dict[str, float | str]]:
        """Return the highest-scoring categories in descending order."""

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
    """Estimate how terminology-dense a chunk is."""

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
    """Weight informative chunks higher during long-document aggregation."""

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
    """Aggregate chunk-by-category similarities into a single score vector."""

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
    """Normalize an embedding to unit length when possible."""

    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def confidence_thresholds_for_chunk_count(num_chunks: int) -> tuple[float, float]:
    """Choose confidence thresholds based on document length."""

    if num_chunks >= 4:
        return LONG_DOCUMENT_SCORE_THRESHOLD, LONG_DOCUMENT_GAP_THRESHOLD
    return LOW_CONFIDENCE_SCORE_THRESHOLD, LOW_CONFIDENCE_GAP_THRESHOLD


def apply_score_boosts(
    base_scores: dict[str, float],
    score_boosts: dict[str, float] | None,
) -> dict[str, float]:
    """Apply bounded score adjustments from rule-based hints."""

    if not score_boosts:
        return dict(base_scores)

    boosted: dict[str, float] = {}
    for code, score in base_scores.items():
        boosted[code] = max(0.0, min(1.0, float(score) + float(score_boosts.get(code, 0.0))))
    return boosted


class EmbeddingCategoryClassifier:
    """Classify documents by scoring chunk embeddings against category prototypes."""

    def __init__(
        self,
        embedder: EmbeddingBackend,
        categories: Sequence[CategoryDefinition] | None = None,
    ) -> None:
        self.embedder = embedder
        self.categories = list(categories or DEFAULT_CATEGORIES)
        self._node_embeddings: dict[str, np.ndarray] = {}
        self._leaf_categories = list(iter_leaf_categories(self.categories))
        self._descendant_leaf_codes = {
            category.code: [leaf.code for leaf in category.leaves()]
            for category in iter_categories(self.categories)
        }

    def _node_embedding(self, category: CategoryDefinition) -> np.ndarray:
        """Return the cached prototype embedding for a taxonomy node."""

        cached = self._node_embeddings.get(category.code)
        if cached is not None:
            return cached

        embedding_inputs = list(category.embedding_texts())
        embeddings = self.embedder.encode(embedding_inputs)
        vector = _normalize_embedding(np.mean(embeddings, axis=0))
        self._node_embeddings[category.code] = vector
        return vector

    def _candidate_embeddings(self, categories: Sequence[CategoryDefinition]) -> np.ndarray:
        """Stack category prototype embeddings into a single matrix."""

        return np.vstack([self._node_embedding(category) for category in categories])

    def _score_candidates(
        self,
        document_embeddings: np.ndarray,
        categories: Sequence[CategoryDefinition],
        chunk_weights: Sequence[float],
        leaf_similarity_map: dict[str, float] | None = None,
        score_boosts: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Score candidate taxonomy nodes for the current chunk set."""

        similarity_matrix = cosine_similarity(document_embeddings, self._candidate_embeddings(categories))
        aggregated = aggregate_similarity_rows(similarity_matrix, chunk_weights)
        direct_scores = {
            category.code: float(score)
            for category, score in zip(categories, aggregated)
        }
        if leaf_similarity_map is None:
            return apply_score_boosts(direct_scores, score_boosts)

        combined_scores: dict[str, float] = {}
        for category in categories:
            descendant_leaf_scores = [
                leaf_similarity_map[leaf_code]
                for leaf_code in self._descendant_leaf_codes[category.code]
                if leaf_code in leaf_similarity_map
            ]
            descendant_score = max(descendant_leaf_scores) if descendant_leaf_scores else direct_scores[category.code]
            combined_scores[category.code] = max(direct_scores[category.code], float(descendant_score))
        return apply_score_boosts(combined_scores, score_boosts)

    def categorize(
        self,
        chunks: Sequence[str],
        score_boosts: dict[str, float] | None = None,
    ) -> CategorizationResult:
        """Return the best category plus confidence diagnostics for a document."""

        if not chunks:
            raise ValueError("categorize() requires at least one chunk")

        chunk_texts = list(chunks)
        document_embeddings = self.embedder.encode(chunk_texts)

        chunk_weights: list[float] = []
        informative_chunk_indices: list[int] = []
        score_threshold, gap_threshold = confidence_thresholds_for_chunk_count(len(chunk_texts))
        for index, chunk in enumerate(chunk_texts):
            weight, informative = compute_chunk_weight(chunk, index=index, total_chunks=len(chunk_texts))
            chunk_weights.append(weight)
            if informative:
                informative_chunk_indices.append(index)

        # Score leaves first, then walk down the taxonomy while keeping the best
        # accepted level. This avoids overcommitting to a low-confidence leaf.
        leaf_similarity_map = self._score_candidates(
            document_embeddings=document_embeddings,
            categories=self._leaf_categories,
            chunk_weights=chunk_weights,
            score_boosts=score_boosts,
        )

        current_candidates = list(self.categories)
        accepted_path: list[CategoryDefinition] = []
        accepted_level: dict[str, Any] | None = None
        classification_trace: list[dict[str, Any]] = []
        low_confidence_reasons: list[str] = []

        while current_candidates:
            level_scores = self._score_candidates(
                document_embeddings=document_embeddings,
                categories=current_candidates,
                chunk_weights=chunk_weights,
                leaf_similarity_map=leaf_similarity_map,
                score_boosts=score_boosts,
            )
            ranked = sorted(level_scores.items(), key=lambda item: item[1], reverse=True)
            best_code, best_score = ranked[0]
            top_2_score = ranked[1][1] if len(ranked) > 1 else 0.0
            confidence_gap = max(0.0, best_score - top_2_score)
            best_node = next(category for category in current_candidates if category.code == best_code)
            low_score = best_score < score_threshold
            small_gap = confidence_gap < gap_threshold
            acceptable = not (low_score or small_gap)

            classification_trace.append(
                {
                    "depth": len(accepted_path) + 1,
                    "candidate_codes": [code for code, _ in ranked[:3]],
                    "selected_code": best_code,
                    "top_1_score": float(best_score),
                    "top_2_score": float(top_2_score),
                    "confidence_gap": float(confidence_gap),
                    "accepted": acceptable,
                }
            )

            if accepted_level is None or acceptable:
                accepted_path.append(best_node)
                accepted_level = {
                    "node": best_node,
                    "score": float(best_score),
                    "top_1_score": float(best_score),
                    "top_2_score": float(top_2_score),
                    "confidence_gap": float(confidence_gap),
                }

            if low_score:
                low_confidence_reasons.append("low_top_score")
            if small_gap:
                low_confidence_reasons.append("small_gap")

            if low_score or small_gap:
                if len(accepted_path) > 1 and accepted_path[-1].code == best_node.code and not acceptable:
                    accepted_path.pop()

                if accepted_level is None:
                    accepted_level = {
                        "node": best_node,
                        "score": float(best_score),
                        "top_1_score": float(best_score),
                        "top_2_score": float(top_2_score),
                        "confidence_gap": float(confidence_gap),
                    }
                    accepted_path = [best_node]

                low_confidence_reasons.append("taxonomy_gap")
                if len(accepted_path) == 1:
                    low_confidence_reasons.append("root_uncertain")
                else:
                    low_confidence_reasons.append("branch_uncertain")
                if accepted_level["node"].children:
                    low_confidence_reasons.append("stopped_before_leaf")
                break

            if best_node.is_leaf:
                break

            current_candidates = list(best_node.children)

        if accepted_level is None:
            raise RuntimeError("classifier failed to select a category")

        final_node = accepted_level["node"]
        unique_reasons = list(dict.fromkeys(low_confidence_reasons))

        return CategorizationResult(
            category=final_node,
            score=max(0.0, min(1.0, accepted_level["score"])),
            similarities=leaf_similarity_map,
            top_1_score=accepted_level["top_1_score"],
            top_2_score=accepted_level["top_2_score"],
            confidence_gap=accepted_level["confidence_gap"],
            low_confidence=bool(unique_reasons),
            low_confidence_reasons=unique_reasons,
            num_chunks_scored=len(chunk_texts),
            informative_chunk_indices=informative_chunk_indices,
            category_path=list(accepted_path),
            category_depth=len(accepted_path),
            category_is_leaf=final_node.is_leaf,
            classification_trace=classification_trace,
        )
