import numpy as np

from nir_tagging_service.category_catalog import (
    CategoryDefinition,
)
from nir_tagging_service.categorization import EmbeddingCategoryClassifier


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
