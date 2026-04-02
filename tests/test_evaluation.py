import json
from pathlib import Path
import re

from nir_tagging_service.category_catalog import CategoryDefinition
from nir_tagging_service.categorization import CategorizationResult
from nir_tagging_service.tag_extraction import TagCandidate


class FakeCategorizer:
    def categorize(self, chunks: list[str]) -> CategorizationResult:
        domain = CategoryDefinition(
            code="technology",
            label="Технологии",
            description="technology domain",
        )
        leaf = CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        )
        return CategorizationResult(
            category=leaf,
            score=0.91,
            similarities={
                "technology_software": 0.91,
                "science_research": 0.42,
            },
            category_path=[domain, leaf],
            category_depth=2,
            category_is_leaf=True,
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


class FakeLongDocumentCategorizer:
    def categorize(self, chunks: list[str]) -> CategorizationResult:
        joined = "\n".join(chunks).lower()
        if "ambiguous" in joined:
            domain = CategoryDefinition(
                code="technology",
                label="Технологии",
                description="technology domain",
            )
            leaf = CategoryDefinition(
                code="technology_software",
                label="Технологии и разработка",
                description="technology",
            )
            return CategorizationResult(
                category=leaf,
                score=0.57,
                similarities={
                    "technology_software": 0.57,
                    "science_research": 0.54,
                },
                top_1_score=0.57,
                top_2_score=0.54,
                confidence_gap=0.03,
                low_confidence=True,
                low_confidence_reasons=["small_gap", "taxonomy_gap"],
                num_chunks_scored=len(chunks),
                informative_chunk_indices=[0, max(0, len(chunks) - 1)],
                category_path=[domain, leaf],
                category_depth=2,
                category_is_leaf=True,
            )

        domain = CategoryDefinition(
            code="technology",
            label="Технологии",
            description="technology domain",
        )
        leaf = CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        )
        return CategorizationResult(
            category=leaf,
            score=0.88,
            similarities={
                "technology_software": 0.88,
                "science_research": 0.34,
            },
            top_1_score=0.88,
            top_2_score=0.34,
            confidence_gap=0.54,
            low_confidence=False,
            low_confidence_reasons=[],
            num_chunks_scored=len(chunks),
            informative_chunk_indices=[0],
            category_path=[domain, leaf],
            category_depth=2,
            category_is_leaf=True,
        )


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
    assert report["exact_leaf_accuracy"] == 1.0
    assert report["path_prefix_accuracy"] == 1.0
    assert report["domain_accuracy"] == 1.0
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


def test_evaluate_dataset_counts_ancestor_prediction_as_prefix_match(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_dataset

    class FakeHierarchicalCategorizer:
        def categorize(self, chunks: list[str]) -> CategorizationResult:
            domain = CategoryDefinition(
                code="technology",
                label="Технологии",
                description="technology domain",
            )
            return CategorizationResult(
                category=domain,
                score=0.72,
                similarities={
                    "technology_software": 0.68,
                    "science_research": 0.31,
                },
                low_confidence=True,
                low_confidence_reasons=["stopped_before_leaf"],
                category_path=[domain],
                category_depth=1,
                category_is_leaf=False,
            )

    dataset_path = tmp_path / "dataset-prefix.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "kind": "short_note",
                    "expected_category": "technology_software",
                    "text": "System design note about APIs, deployment and retrieval.",
                }
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_dataset(
        dataset_path=dataset_path,
        categorizer=FakeHierarchicalCategorizer(),
        tagger=FakeTagger(),
    )

    assert report["category_accuracy"] == 0.0
    assert report["exact_leaf_accuracy"] == 0.0
    assert report["path_prefix_accuracy"] == 1.0
    assert report["domain_accuracy"] == 1.0


def test_evaluate_dataset_loads_relative_file_path_from_dataset_directory(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_dataset

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    sample_path = documents_dir / "sample.txt"
    sample_path.write_text(
        "Transformer embeddings improve semantic search quality.",
        encoding="utf-8",
    )

    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "kind": "short_note",
                    "expected_category": "technology_software",
                    "file_path": "documents/sample.txt",
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


def test_example_datasets_are_local_and_have_mixed_ru_en_samples() -> None:
    category_dataset = json.loads(
        Path("examples/quality-evaluation-dataset.json").read_text(encoding="utf-8")
    )
    tag_dataset = json.loads(
        Path("examples/tag-quality-evaluation-dataset.json").read_text(encoding="utf-8")
    )

    for dataset in (category_dataset, tag_dataset):
        assert all(("text" in sample) or ("file_path" in sample) for sample in dataset)
        assert all("title" not in sample for sample in dataset)

    assert any("file_path" in sample for sample in category_dataset)
    for sample in category_dataset:
        file_path = sample.get("file_path")
        if not file_path:
            continue
        resolved = Path("examples/quality-evaluation-dataset.json").parent / file_path
        assert resolved.exists()

    assert any("metadata" not in sample or "title" not in sample.get("metadata", {}) for sample in category_dataset)
    assert any("metadata" not in sample or "title" not in sample.get("metadata", {}) for sample in tag_dataset)

    category_texts: list[str] = []
    for sample in category_dataset:
        if "text" in sample:
            category_texts.append(sample["text"])
        else:
            category_texts.append(
                (Path("examples/quality-evaluation-dataset.json").parent / sample["file_path"]).read_text(encoding="utf-8")
            )
    tag_texts = [sample["text"] for sample in tag_dataset]
    assert any(re.search(r"[А-Яа-яЁё]", text) for text in category_texts)
    assert any(re.search(r"[A-Za-z]", text) for text in category_texts)
    assert any(re.search(r"[А-Яа-яЁё]", text) for text in tag_texts)
    assert any(re.search(r"[A-Za-z]", text) for text in tag_texts)


def test_evaluate_long_document_dataset_reports_accuracy_and_low_confidence(tmp_path) -> None:
    from nir_tagging_service.evaluation import evaluate_long_document_dataset

    dataset_path = tmp_path / "long-doc-dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "kind": "long_document",
                    "expected_category": "technology_software",
                    "text": "Architecture overview. " * 300,
                },
                {
                    "kind": "long_document",
                    "expected_category": "technology_software",
                    "metadata": {"title": "Ambiguous platform and research overview"},
                    "text": "Ambiguous mixed benchmarking and platform architecture overview. " * 300,
                },
            ]
        ),
        encoding="utf-8",
    )

    report = evaluate_long_document_dataset(
        dataset_path=dataset_path,
        categorizer=FakeLongDocumentCategorizer(),
        tagger=FakeTagger(),
    )

    assert report["total_cases"] == 2
    assert report["long_document_accuracy"] == 1.0
    assert report["exact_leaf_accuracy"] == 1.0
    assert report["path_prefix_accuracy"] == 1.0
    assert report["domain_accuracy"] == 1.0
    assert report["top_2_accuracy"] == 1.0
    assert report["low_confidence_rate"] == 0.5
    assert report["low_confidence_accuracy"] == 1.0


def test_long_document_example_dataset_is_self_contained() -> None:
    dataset = json.loads(
        Path("examples/long-document-evaluation-dataset.json").read_text(encoding="utf-8")
    )

    assert all(sample["kind"] == "long_document" for sample in dataset)
    assert all("file_path" in sample for sample in dataset)
    assert all("text" not in sample for sample in dataset)
    assert any(sample.get("expected_low_confidence") is True for sample in dataset)
    for sample in dataset:
        resolved = Path("examples/long-document-evaluation-dataset.json").parent / sample["file_path"]
        assert resolved.exists()


def test_source_material_examples_reference_local_text_files_and_cover_multiple_domains() -> None:
    dataset_path = Path("examples/source-material-examples.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert len(dataset) >= 8
    assert any(sample.get("file_path") for sample in dataset)
    assert any("text" in sample for sample in dataset)
    assert {
        "technology_software_tooling",
        "technology_software_architecture",
        "education_course_material",
        "education_assessment_guidelines",
        "research_literature_review",
    } <= {
        sample["expected_category"] for sample in dataset
    }
    assert any("3D-сцену" in sample.get("text", "") for sample in dataset)
    assert any("MimikaStudio" in sample.get("text", "") for sample in dataset)

    for sample in dataset:
        assert sample["kind"] in {"short_note", "long_document"}
        assert ("text" in sample) or ("file_path" in sample)
        if "file_path" in sample:
            resolved = dataset_path.parent / sample["file_path"]
            assert resolved.exists()
            text = resolved.read_text(encoding="utf-8")
            assert text.strip()
