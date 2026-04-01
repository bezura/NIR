import json
from pathlib import Path

from nir_tagging_service.category_catalog import CategoryDefinition
from nir_tagging_service.categorization import CategorizationResult


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
    def extract_tags(self, chunks: list[str], max_tags: int = 5) -> list[object]:
        return []


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
