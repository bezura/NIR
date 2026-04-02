import numpy as np

from nir_tagging_service.category_catalog import (
    CategoryDefinition,
)
from nir_tagging_service.categorization import (
    EmbeddingCategoryClassifier,
    aggregate_similarity_rows,
    compute_chunk_weight,
    confidence_thresholds_for_chunk_count,
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


def test_categorizer_walks_hierarchy_to_leaf_when_each_level_is_confident() -> None:
    categories = [
        CategoryDefinition(
            code="technology",
            label="Technology",
            description="technology domain",
            children=(
                CategoryDefinition(
                    code="technology_software",
                    label="Software",
                    description="software engineering",
                    children=(
                        CategoryDefinition(
                            code="technology_software_backend",
                            label="Backend",
                            description="backend services apis",
                        ),
                        CategoryDefinition(
                            code="technology_software_ml",
                            label="ML Systems",
                            description="ml pipelines models",
                        ),
                    ),
                ),
                CategoryDefinition(
                    code="technology_data",
                    label="Data",
                    description="data platform analytics",
                ),
            ),
        ),
        CategoryDefinition(
            code="research",
            label="Research",
            description="research domain",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology domain": [1.0, 0.0, 0.0],
                "software engineering": [0.9, 0.1, 0.0],
                "backend services apis": [0.95, 0.05, 0.0],
                "ml pipelines models": [0.3, 0.7, 0.0],
                "data platform analytics": [0.4, 0.6, 0.0],
                "research domain": [0.0, 1.0, 0.0],
                "doc": [0.97, 0.08, 0.0],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["doc"])

    assert result.category.code == "technology_software_backend"
    assert [node.code for node in result.category_path] == [
        "technology",
        "technology_software",
        "technology_software_backend",
    ]
    assert result.category_is_leaf is True
    assert result.category_depth == 3
    assert result.low_confidence is False
    assert len(result.classification_trace) == 3


def test_categorizer_stops_at_last_confident_branch_when_next_level_is_ambiguous() -> None:
    categories = [
        CategoryDefinition(
            code="technology",
            label="Technology",
            description="technology domain",
            children=(
                CategoryDefinition(
                    code="technology_software",
                    label="Software",
                    description="software engineering",
                    children=(
                        CategoryDefinition(
                            code="technology_software_backend",
                            label="Backend",
                            description="backend services apis",
                        ),
                        CategoryDefinition(
                            code="technology_software_ml",
                            label="ML Systems",
                            description="ml pipelines models",
                        ),
                    ),
                ),
                CategoryDefinition(
                    code="technology_data",
                    label="Data",
                    description="data platform analytics",
                ),
            ),
        ),
        CategoryDefinition(
            code="research",
            label="Research",
            description="research domain",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology domain": [0.95, 0.05, 0.0],
                "software engineering": [0.94, 0.06, 0.0],
                "backend services apis": [0.72, 0.68, 0.0],
                "ml pipelines models": [0.68, 0.72, 0.0],
                "data platform analytics": [0.2, 0.8, 0.0],
                "research domain": [0.0, 1.0, 0.0],
                "ambiguous-doc": [0.95, 0.3, 0.0],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["ambiguous-doc"])

    assert result.category.code == "technology_software"
    assert [node.code for node in result.category_path] == [
        "technology",
        "technology_software",
    ]
    assert result.category_is_leaf is False
    assert result.category_depth == 2
    assert result.low_confidence is True
    assert "small_gap" in result.low_confidence_reasons
    assert "stopped_before_leaf" in result.low_confidence_reasons


def test_categorizer_uses_descendant_leaf_signal_to_choose_broad_parent_branch() -> None:
    categories = [
        CategoryDefinition(
            code="technology",
            label="Technology",
            description="broad generic domain",
            children=(
                CategoryDefinition(
                    code="technology_software",
                    label="Software",
                    description="also broad generic branch",
                    children=(
                        CategoryDefinition(
                            code="technology_software_retrieval",
                            label="Retrieval",
                            description="semantic search vector database reranking retrieval pipeline",
                        ),
                    ),
                ),
            ),
        ),
        CategoryDefinition(
            code="education",
            label="Education",
            description="broad education domain",
            children=(
                CategoryDefinition(
                    code="education_course_material",
                    label="Course",
                    description="course syllabus lectures assignments tutorials",
                ),
            ),
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "broad generic domain": [0.55, 0.45, 0.7],
                "also broad generic branch": [0.57, 0.43, 0.7],
                "semantic search vector database reranking retrieval pipeline": [1.0, 0.0, 0.0],
                "broad education domain": [0.45, 0.55, 0.7],
                "course syllabus lectures assignments tutorials": [0.0, 1.0, 0.0],
                "doc": [0.98, 0.02, 0.0],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["doc"])

    assert result.category.code == "technology_software_retrieval"
    assert [node.code for node in result.category_path] == [
        "technology",
        "technology_software",
        "technology_software_retrieval",
    ]
    assert result.low_confidence is False


def test_categorizer_prefers_introduction_and_conclusion_signal_for_long_document() -> None:
    categories = [
        CategoryDefinition(
            code="technology",
            label="Technology",
            description="technology",
            children=(
                CategoryDefinition(
                    code="technology_software",
                    label="Software",
                    description="software",
                    children=(
                        CategoryDefinition(
                            code="technology_software_architecture",
                            label="Architecture",
                            description="platform architecture api gateway jobs polling observability",
                        ),
                        CategoryDefinition(
                            code="technology_software_retrieval",
                            label="Retrieval",
                            description="retrieval pipeline vector database reranking semantic search",
                        ),
                    ),
                ),
            ),
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "technology": [1.0, 0.0, 0.0],
                "software": [1.0, 0.0, 0.0],
                "platform architecture api gateway jobs polling observability": [0.95, 0.05, 0.0],
                "retrieval pipeline vector database reranking semantic search": [0.05, 0.95, 0.0],
                "title-context": [0.96, 0.04, 0.0],
                "intro-chunk": [0.93, 0.07, 0.0],
                "noisy-middle": [0.03, 0.97, 0.0],
                "conclusion-chunk": [0.9, 0.1, 0.0],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(
        ["title-context", "intro-chunk", "noisy-middle", "conclusion-chunk"]
    )

    assert result.category.code == "technology_software_architecture"
    assert result.low_confidence is False


def test_categorizer_descends_when_branch_leaf_has_clear_margin_even_if_parent_score_is_lower() -> None:
    categories = [
        CategoryDefinition(
            code="technology",
            label="Technology",
            description="broad technology",
            children=(
                CategoryDefinition(
                    code="technology_software",
                    label="Software",
                    description="generic software",
                    children=(
                        CategoryDefinition(
                            code="technology_software_architecture",
                            label="Architecture",
                            description="platform architecture jobs polling observability api gateway",
                        ),
                        CategoryDefinition(
                            code="technology_software_retrieval",
                            label="Retrieval",
                            description="retrieval pipeline vector database reranking semantic search",
                        ),
                    ),
                ),
            ),
        ),
        CategoryDefinition(
            code="research",
            label="Research",
            description="broad research",
        ),
    ]
    classifier = EmbeddingCategoryClassifier(
        embedder=FakeEmbedder(
            {
                "broad technology": [0.7, 0.3, 0.65],
                "generic software": [0.68, 0.32, 0.65],
                "platform architecture jobs polling observability api gateway": [0.98, 0.02, 0.0],
                "retrieval pipeline vector database reranking semantic search": [0.55, 0.45, 0.0],
                "broad research": [0.3, 0.7, 0.65],
                "doc": [0.98, 0.02, 0.0],
            }
        ),
        categories=categories,
    )

    result = classifier.categorize(["doc"])

    assert result.category.code == "technology_software_architecture"
    assert [node.code for node in result.category_path] == [
        "technology",
        "technology_software",
        "technology_software_architecture",
    ]
    assert result.low_confidence is False


def test_long_documents_use_more_permissive_confidence_thresholds() -> None:
    short_score_threshold, short_gap_threshold = confidence_thresholds_for_chunk_count(2)
    long_score_threshold, long_gap_threshold = confidence_thresholds_for_chunk_count(5)

    assert long_score_threshold < short_score_threshold
    assert long_gap_threshold < short_gap_threshold


def test_categorizer_applies_external_score_boosts_before_selecting_category() -> None:
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
                "document": [0.73, 0.68],
            }
        ),
        categories=categories,
    )

    unboosted = classifier.categorize(["document"])
    boosted = classifier.categorize(["document"], score_boosts={"science_research": 0.06})

    assert unboosted.category.code == "technology_software"
    assert boosted.category.code == "science_research"
    assert boosted.similarities["science_research"] > boosted.similarities["technology_software"]
