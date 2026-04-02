from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
        candidate = _repo_root() / candidate

    return candidate.read_text(encoding="utf-8")


def _safe_accuracy(values: list[bool]) -> float | None:
    if not values:
        return None

    return sum(values) / len(values)


def evaluate_dataset(dataset_path: Path, categorizer: Any, tagger: Any) -> dict[str, Any]:
    samples = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    for sample in samples:
        text = _load_dataset_text(sample, Path(dataset_path))
        source = "document" if sample["kind"] == "long_document" else "article"
        prepared = prepare_text(text, source)
        category_result = categorizer.categorize(prepared.categorization_chunks)
        tagger.extract_tags(prepared.tag_extraction_chunks, max_tags=5)

        rows.append(
            {
                "kind": sample["kind"],
                "expected_category": sample["expected_category"],
                "predicted_category": category_result.category.code,
                "top_2_codes": [item["code"] for item in category_result.top_k(2)],
            }
        )

    exact_matches = [row["predicted_category"] == row["expected_category"] for row in rows]
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

    return {
        "total_cases": len(rows),
        "category_accuracy": _safe_accuracy(exact_matches),
        "top_2_accuracy": _safe_accuracy(top_2_matches),
        "short_document_accuracy": _safe_accuracy(short_matches),
        "long_document_accuracy": _safe_accuracy(long_matches),
    }


def evaluate_tag_dataset(dataset_path: Path, tagger: Any, max_tags: int = 5) -> dict[str, Any]:
    samples = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    total_matches = 0
    total_predictions = 0
    expected_matches: list[float] = []

    for sample in samples:
        text = _load_dataset_text(sample, Path(dataset_path))
        source = "document" if sample["kind"] == "long_document" else "article"
        metadata = sample.get("metadata") or {}
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
    tag_dataset_path = _repo_root() / "examples" / "tag-quality-evaluation-dataset.json"
    services = build_default_pipeline_services(get_settings())
    report = {
        "categories": evaluate_dataset(
            dataset_path=category_dataset_path,
            categorizer=services.categorizer,
            tagger=services.tagger,
        )
    }
    if tag_dataset_path.exists():
        report["tags"] = evaluate_tag_dataset(
            dataset_path=tag_dataset_path,
            tagger=services.tagger,
        )
    print(format_report(report))


if __name__ == "__main__":
    main()
