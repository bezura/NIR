import json
from pathlib import Path


def test_external_assignment7_dataset_exists_and_has_expected_sources() -> None:
    dataset_path = Path("examples/external-web-evaluation-dataset.json")

    assert dataset_path.exists(), "expected external Habr/Wikipedia dataset for assignment 7"

    samples = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert len(samples) >= 6

    source_sites = {sample.get("source_site") for sample in samples}
    assert {"habr", "wikipedia"}.issubset(source_sites)

    for sample in samples:
        assert sample["kind"] == "short_note"
        assert sample["expected_category"]
        assert len(sample.get("expected_tags", [])) >= 3
        assert sample.get("source_url", "").startswith("https://")

