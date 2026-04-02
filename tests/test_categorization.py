import numpy as np

from nir_tagging_service.category_catalog import (
    CategoryDefinition,
)
from nir_tagging_service.categorization import (
    EmbeddingCategoryClassifier,
    aggregate_similarity_rows,
    compute_chunk_weight,
)


class FakeEmbedder:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.mapping = {key: np.array(value, dtype=float) for key, value in mapping.items()}

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self.mapping[text] for text in texts])


def test_categorizer_chooses_best_category_by_cosine_similarity() -> None:
    categories = [
        CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        ),
        CategoryDefinition(
            code="science_research",
            label="Наука и исследования",
            description="science",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology": [1.0, 0.0],
                "science": [0.0, 1.0],
                "document": [0.9, 0.1],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["document"])

    assert result.category.code == "technology_software"
    assert result.score > 0.9
    assert result.similarities["technology_software"] > result.similarities["science_research"]


def test_categorizer_averages_multiple_chunk_embeddings() -> None:
    categories = [
        CategoryDefinition(
            code="business_product",
            label="Бизнес и продукт",
            description="business",
        ),
        CategoryDefinition(
            code="education_learning",
            label="Образование и обучение",
            description="education",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "business": [1.0, 0.0],
                "education": [0.0, 1.0],
                "chunk-a": [1.0, 0.0],
                "chunk-b": [0.8, 0.2],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["chunk-a", "chunk-b"])

    assert result.category.code == "business_product"
    assert result.score > 0.8


def test_categorization_result_can_return_top_k_scores() -> None:
    categories = [
        CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        ),
        CategoryDefinition(
            code="science_research",
            label="Наука и исследования",
            description="science",
        ),
        CategoryDefinition(
            code="education_learning",
            label="Образование и обучение",
            description="education",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology": [1.0, 0.0],
                "science": [0.4, 0.6],
                "education": [0.0, 1.0],
                "document": [0.9, 0.1],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["document"])

    assert [item["code"] for item in result.top_k(2)] == [
        "technology_software",
        "science_research",
    ]
    assert result.top_k(2)[0]["score"] >= result.top_k(2)[1]["score"]


def test_aggregate_similarity_rows_combines_weighted_mean_with_max_bonus() -> None:
    similarities = np.array(
        [
            [0.22, 0.97],
            [0.22, 0.96],
            [0.99, 0.10],
        ],
        dtype=float,
    )
    weights = [1.0, 1.0, 2.2]

    aggregated = aggregate_similarity_rows(similarities, weights)

    assert aggregated[0] > aggregated[1]


def test_compute_chunk_weight_prefers_conclusion_like_dense_chunks() -> None:
    generic_chunk = "The study reviews prior work and describes the dataset in broad terms."
    conclusion_chunk = (
        "Conclusion: retrieval architecture embeddings vector database reranking observability "
        "indexing orchestration semantic search."
    )

    generic_weight, generic_informative = compute_chunk_weight(
        generic_chunk,
        index=0,
        total_chunks=3,
    )
    conclusion_weight, conclusion_informative = compute_chunk_weight(
        conclusion_chunk,
        index=2,
        total_chunks=3,
    )

    assert conclusion_weight > generic_weight
    assert conclusion_informative is True
    assert generic_informative is False


def test_categorizer_marks_result_low_confidence_when_gap_is_small() -> None:
    categories = [
        CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        ),
        CategoryDefinition(
            code="science_research",
            label="Наука и исследования",
            description="science",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology": [1.0, 0.0],
                "science": [0.0, 1.0],
                "ambiguous-document": [0.72, 0.68],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["ambiguous-document"])

    assert result.low_confidence is True
    assert "small_gap" in result.low_confidence_reasons
    assert result.top_1_score >= result.top_2_score
    assert result.confidence_gap < 0.08
