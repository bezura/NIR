from types import SimpleNamespace

from nir_tagging_service.rules import apply_rule_hints


LANGUAGE_PROFILE = SimpleNamespace(
    dominant_language="en",
    secondary_language=None,
    mixed_language=False,
    distribution={"en": 1.0, "ru": 0.0, "other": 0.0},
)


def test_rule_hints_boost_architecture_leaf_for_architecture_titles() -> None:
    hints = apply_rule_hints(
        source="document",
        metadata={"title": "Architecture of a Multilingual Retrieval Platform"},
        title_text="Architecture of a Multilingual Retrieval Platform",
        metadata_terms=["semantic search"],
        language_profile=LANGUAGE_PROFILE,
        output_language="en",
    )

    assert hints.category_boosts["technology_software_architecture"] > 0.0


def test_rule_hints_boost_literature_review_when_metadata_mentions_it() -> None:
    hints = apply_rule_hints(
        source="document",
        metadata={"keywords": ["literature review", "multilingual evaluation"]},
        title_text="",
        metadata_terms=["literature review", "multilingual evaluation"],
        language_profile=LANGUAGE_PROFILE,
        output_language="en",
    )

    assert hints.category_boosts["research_literature_review"] > 0.0


def test_rule_hints_boost_practicum_leaf_for_practicum_titles() -> None:
    hints = apply_rule_hints(
        source="document",
        metadata={"title": "Text Analysis Practicum and Course Plan"},
        title_text="Text Analysis Practicum and Course Plan",
        metadata_terms=[],
        language_profile=LANGUAGE_PROFILE,
        output_language="en",
    )

    assert hints.category_boosts["education_practicum_lab"] > 0.0
