from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nir_tagging_service.category_catalog import DEFAULT_CATEGORIES, iter_categories
from nir_tagging_service.preprocessing import prepare_text
from nir_tagging_service.tag_extraction import KeywordTagger


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dataset_text(sample: dict[str, Any], dataset_path: Path) -> str:
    text = sample.get("text")
    if text is not None:
        return text

    file_path = sample.get("file_path")
    if not file_path:
        raise ValueError("dataset sample must include either 'text' or 'file_path'")

    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = dataset_path.parent / candidate

    return candidate.read_text(encoding="utf-8")


def _load_sample_metadata(sample: dict[str, Any]) -> dict[str, Any]:
    metadata = sample.get("metadata")
    normalized: dict[str, Any] = dict(metadata) if isinstance(metadata, dict) else {}

    legacy_title = sample.get("title")
    if isinstance(legacy_title, str) and legacy_title.strip() and "title" not in normalized:
        normalized["title"] = legacy_title.strip()

    return normalized


def _safe_accuracy(values: list[bool]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


def _taxonomy_paths() -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {}

    def visit(node, prefix: list[str]) -> None:
        current = [*prefix, node.code]
        paths[node.code] = current
        for child in node.children:
            visit(child, current)

    for root in DEFAULT_CATEGORIES:
        visit(root, [])

    return paths


def _predicted_path_codes(category_result: Any) -> list[str]:
    category_path = getattr(category_result, "category_path", None) or []
    if category_path:
        return [node.code for node in category_path]
    return [category_result.category.code]


def _evaluate_category_rows(
    samples: list[dict[str, Any]],
    dataset_path: Path,
    categorizer: Any,
    tagger: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for sample in samples:
        text = _load_dataset_text(sample, dataset_path)
        source = "document" if sample["kind"] == "long_document" else "article"
        metadata = _load_sample_metadata(sample)
        prepared = prepare_text(text, source, metadata=metadata)
        category_result = categorizer.categorize(prepared.categorization_chunks)
        tagger.extract_tags(prepared.tag_extraction_chunks, max_tags=5)

        rows.append(
            {
                "kind": sample["kind"],
                "expected_category": sample["expected_category"],
                "predicted_category": category_result.category.code,
                "predicted_path": _predicted_path_codes(category_result),
                "top_2_codes": [item["code"] for item in category_result.top_k(2)],
                "low_confidence": category_result.low_confidence,
                "expected_low_confidence": sample.get("expected_low_confidence"),
            }
        )

    return rows


def evaluate_dataset(dataset_path: Path, categorizer: Any, tagger: Any) -> dict[str, Any]:
    samples = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    rows = _evaluate_category_rows(
        samples,
        dataset_path=Path(dataset_path),
        categorizer=categorizer,
        tagger=tagger,
    )
    taxonomy_paths = _taxonomy_paths()

    exact_matches = [row["predicted_category"] == row["expected_category"] for row in rows]
    prefix_matches = [
        row["predicted_category"] in taxonomy_paths.get(row["expected_category"], [row["expected_category"]])
        for row in rows
    ]
    domain_matches = [
        bool(row["predicted_path"])
        and bool(taxonomy_paths.get(row["expected_category"]))
        and row["predicted_path"][0] == taxonomy_paths[row["expected_category"]][0]
        for row in rows
    ]
    top_2_matches = [row["expected_category"] in row["top_2_codes"] for row in rows]
    short_matches = [
        row["predicted_category"] == row["expected_category"]
        for row in rows
        if row["kind"] != "long_document"
    ]
    long_matches = [
        row["predicted_category"] == row["expected_category"]
        for row in rows
        if row["kind"] == "long_document"
    ]
    low_confidence_rows = [row for row in rows if row["low_confidence"]]
    low_confidence_matches = [
        row["predicted_category"] == row["expected_category"]
        for row in low_confidence_rows
    ]

    return {
        "total_cases": len(rows),
        "category_accuracy": _safe_accuracy(exact_matches),
        "exact_leaf_accuracy": _safe_accuracy(exact_matches),
        "path_prefix_accuracy": _safe_accuracy(prefix_matches),
        "domain_accuracy": _safe_accuracy(domain_matches),
        "top_2_accuracy": _safe_accuracy(top_2_matches),
        "short_document_accuracy": _safe_accuracy(short_matches),
        "long_document_accuracy": _safe_accuracy(long_matches),
        "low_confidence_rate": _safe_accuracy([row["low_confidence"] for row in rows]),
        "low_confidence_accuracy": _safe_accuracy(low_confidence_matches),
    }


def evaluate_long_document_dataset(dataset_path: Path, categorizer: Any, tagger: Any) -> dict[str, Any]:
    samples = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    long_document_samples = [
        sample for sample in samples
        if sample.get("kind") == "long_document"
    ]
    rows = _evaluate_category_rows(
        long_document_samples,
        dataset_path=Path(dataset_path),
        categorizer=categorizer,
        tagger=tagger,
    )
    taxonomy_paths = _taxonomy_paths()

    exact_matches = [row["predicted_category"] == row["expected_category"] for row in rows]
    prefix_matches = [
        row["predicted_category"] in taxonomy_paths.get(row["expected_category"], [row["expected_category"]])
        for row in rows
    ]
    domain_matches = [
        bool(row["predicted_path"])
        and bool(taxonomy_paths.get(row["expected_category"]))
        and row["predicted_path"][0] == taxonomy_paths[row["expected_category"]][0]
        for row in rows
    ]
    top_2_matches = [row["expected_category"] in row["top_2_codes"] for row in rows]
    low_confidence_rows = [row for row in rows if row["low_confidence"]]
    low_confidence_matches = [
        row["predicted_category"] == row["expected_category"]
        for row in low_confidence_rows
    ]
    expected_low_confidence_rows = [
        row for row in rows
        if row["expected_low_confidence"] is not None
    ]
    expected_low_confidence_matches = [
        row["low_confidence"] == row["expected_low_confidence"]
        for row in expected_low_confidence_rows
    ]

    return {
        "total_cases": len(rows),
        "long_document_accuracy": _safe_accuracy(exact_matches),
        "exact_leaf_accuracy": _safe_accuracy(exact_matches),
        "path_prefix_accuracy": _safe_accuracy(prefix_matches),
        "domain_accuracy": _safe_accuracy(domain_matches),
        "top_2_accuracy": _safe_accuracy(top_2_matches),
        "low_confidence_rate": _safe_accuracy([row["low_confidence"] for row in rows]),
        "low_confidence_accuracy": _safe_accuracy(low_confidence_matches),
        "expected_low_confidence_match_rate": _safe_accuracy(expected_low_confidence_matches),
    }


def evaluate_tag_dataset(dataset_path: Path, tagger: Any, max_tags: int = 5) -> dict[str, Any]:
    samples = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    total_matches = 0
    total_predictions = 0
    expected_matches: list[float] = []

    for sample in samples:
        text = _load_dataset_text(sample, Path(dataset_path))
        source = "document" if sample["kind"] == "long_document" else "article"
        metadata = _load_sample_metadata(sample)
        prepared = prepare_text(text, source, metadata=metadata)
        predicted = tagger.extract_tags(
            prepared.tag_extraction_chunks,
            max_tags=max_tags,
            language_profile=prepared.language_profile,
            title_text=prepared.title_text,
        )
        predicted_labels = [
            KeywordTagger.normalize_keyword(tag.normalized_label)
            for tag in predicted[:max_tags]
        ]
        expected_labels = {
            KeywordTagger.normalize_keyword(label)
            for label in sample.get("expected_tags", [])
        }
        matched = sum(1 for label in predicted_labels if label in expected_labels)
        total_matches += matched
        total_predictions += len(predicted_labels)
        expected_matches.append(float(matched))

    precision_at_5 = None
    if total_predictions:
        precision_at_5 = round(total_matches / total_predictions, 3)

    return {
        "total_cases": len(samples),
        "precision_at_5": precision_at_5,
        "average_expected_matches": _safe_accuracy(
            [match / 1.0 for match in expected_matches]
        )
        if expected_matches
        else None,
    }


def format_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def main() -> None:
    from nir_tagging_service.bootstrap import build_default_pipeline_services
    from nir_tagging_service.config import get_settings

    category_dataset_path = _repo_root() / "examples" / "quality-evaluation-dataset.json"
    long_document_dataset_path = _repo_root() / "examples" / "long-document-evaluation-dataset.json"
    tag_dataset_path = _repo_root() / "examples" / "tag-quality-evaluation-dataset.json"
    services = build_default_pipeline_services(get_settings())
    report = {
        "categories": evaluate_dataset(
            dataset_path=category_dataset_path,
            categorizer=services.categorizer,
            tagger=services.tagger,
        )
    }
    if long_document_dataset_path.exists():
        report["long_documents"] = evaluate_long_document_dataset(
            dataset_path=long_document_dataset_path,
            categorizer=services.categorizer,
            tagger=services.tagger,
        )
    if tag_dataset_path.exists():
        report["tags"] = evaluate_tag_dataset(
            dataset_path=tag_dataset_path,
            tagger=services.tagger,
        )
    print(format_report(report))


if __name__ == "__main__":
    main()
