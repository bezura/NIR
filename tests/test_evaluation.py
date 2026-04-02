import json
from pathlib import Path

from nir_tagging_service.category_catalog import CategoryDefinition
from nir_tagging_service.categorization import CategorizationResult
from nir_tagging_service.tag_extraction import TagCandidate


class FakeCategorizer:
    def categorize(self, chunks: list[str]) -> CategorizationResult:
        return CategorizationResult(
            category=CategoryDefinition(
                code="technology_software",
                label="Технологии и разработка",
                description="technology",
            ),
            score=0.91,
            similarities={
                "technology_software": 0.91,
                "science_research": 0.42,
            },
        )


class FakeTagger:
    def extract_tags(
        self,
        chunks: list[str],
        max_tags: int = 5,
        language_profile=None,
        title_text: str = "",
    ) -> list[object]:
        return []


class FakeBenchmarkTagger:
    def extract_tags(
        self,
        chunks: list[str],
        max_tags: int = 5,
        language_profile=None,
        title_text: str = "",
    ) -> list[TagCandidate]:
        joined = "\n".join(chunks)
        if "rag" in joined.lower():
            return [
                TagCandidate(label="semantic search", normalized_label="semantic search", score=0.91),
                TagCandidate(label="rag системы", normalized_label="rag системы", score=0.88),
                TagCandidate(label="поиск", normalized_label="поиск", score=0.52),
            ]

        return [
            TagCandidate(label="векторные базы данных", normalized_label="векторные базы данных", score=0.93),
            TagCandidate(label="semantic retrieval", normalized_label="semantic retrieval", score=0.74),
        ]


def test_evaluate_dataset_returns_accuracy_summary(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_dataset

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "title": "Embeddings for semantic search",
                    "kind": "short_note",
                    "expected_category": "technology_software",
                    "text": "Transformer embeddings improve semantic search quality.",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_dataset(
        dataset_path=dataset_path,
        categorizer=FakeCategorizer(),
        tagger=FakeTagger(),
    )

    assert report["total_cases"] == 1
    assert report["category_accuracy"] == 1.0
    assert report["top_2_accuracy"] == 1.0
    assert report["short_document_accuracy"] == 1.0
    assert report["long_document_accuracy"] is None


def test_evaluate_tag_dataset_returns_precision_summary(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_tag_dataset

    dataset_path = tmp_path / "tag-dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "kind": "short_note",
                    "text": "RAG-системы применяются для semantic search по корпоративным документам.",
                    "metadata": {"title": "Semantic Search в RAG-системах"},
                    "expected_tags": ["semantic search", "rag системы"],
                },
                {
                    "kind": "short_note",
                    "text": "Векторные базы данных используются для семантического поиска.",
                    "expected_tags": ["векторные базы данных"],
                },
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_tag_dataset(dataset_path=dataset_path, tagger=FakeBenchmarkTagger())

    assert report["total_cases"] == 2
    assert report["precision_at_5"] == 0.6
    assert report["average_expected_matches"] == 1.5
