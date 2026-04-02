import json
from pathlib import Path
import re

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


def test_evaluate_dataset_accepts_samples_without_title(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_dataset

    dataset_path = tmp_path / "dataset-no-title.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "kind": "short_note",
                    "expected_category": "technology_software",
                    "text": "Transformer embeddings improve semantic search quality.",
                },
                {
                    "kind": "short_note",
                    "expected_category": "technology_software",
                    "metadata": {"keywords": ["vector search"]},
                    "text": "Vector search helps document retrieval.",
                },
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_dataset(
        dataset_path=dataset_path,
        categorizer=FakeCategorizer(),
        tagger=FakeTagger(),
    )

    assert report["total_cases"] == 2
    assert report["category_accuracy"] == 1.0


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


def test_example_datasets_are_self_contained_and_have_mixed_ru_en_samples() -> None:
    category_dataset = json.loads(
        Path("examples/quality-evaluation-dataset.json").read_text(encoding="utf-8")
    )
    tag_dataset = json.loads(
        Path("examples/tag-quality-evaluation-dataset.json").read_text(encoding="utf-8")
    )

    for dataset in (category_dataset, tag_dataset):
        assert all("text" in sample for sample in dataset)
        assert all("file_path" not in sample for sample in dataset)
        assert all("title" not in sample for sample in dataset)

    assert any("metadata" not in sample or "title" not in sample.get("metadata", {}) for sample in category_dataset)
    assert any("metadata" not in sample or "title" not in sample.get("metadata", {}) for sample in tag_dataset)

    category_texts = [sample["text"] for sample in category_dataset]
    tag_texts = [sample["text"] for sample in tag_dataset]
    assert any(re.search(r"[А-Яа-яЁё]", text) for text in category_texts)
    assert any(re.search(r"[A-Za-z]", text) for text in category_texts)
    assert any(re.search(r"[А-Яа-яЁё]", text) for text in tag_texts)
    assert any(re.search(r"[A-Za-z]", text) for text in tag_texts)
