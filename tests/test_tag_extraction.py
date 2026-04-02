from types import SimpleNamespace

from nir_tagging_service.schemas import TagCatalogEntry
from nir_tagging_service.tag_extraction import KeywordTagger, TagCandidate, reconcile_tag_candidates


class FakeKeywordExtractor:
    def __init__(self, keywords: list[tuple[str, float]]) -> None:
        self.keywords = keywords
        self.seen_text: str | None = None
        self.seen_top_n: int | None = None

    def extract(self, text: str, top_n: int) -> list[tuple[str, float]]:
        self.seen_text = text
        self.seen_top_n = top_n
        return self.keywords


def test_keyword_tagger_normalizes_deduplicates_and_limits_results() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("Machine Learning", 0.91),
            ("machine   learning", 0.87),
            ("NLP", 0.82),
            (" semantic search ", 0.74),
            ("AI", 0.70),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(
        ["Machine learning systems improve semantic search relevance."],
        max_tags=3,
    )

    assert [tag.normalized_label for tag in tags] == [
        "machine learning",
        "nlp",
        "semantic search",
    ]
    assert tags[0].score == 0.91
    assert extractor.seen_top_n == 9


def test_keyword_tagger_uses_all_chunks_for_extraction_context() -> None:
    extractor = FakeKeywordExtractor([("transformer embeddings", 0.88)])
    tagger = KeywordTagger(extractor=extractor)

    tagger.extract_tags(
        [
            "Transformer embeddings improve semantic retrieval.",
            "Keyphrase extraction adds explainability to search results.",
        ],
        max_tags=5,
    )

    assert extractor.seen_text == (
        "Transformer embeddings improve semantic retrieval.\n\n"
        "Keyphrase extraction adds explainability to search results."
    )


def test_keyword_tagger_filters_substrings_and_stopword_edges() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("machine learning", 0.92),
            ("learning", 0.91),
            ("keyphrase extraction", 0.83),
            ("keyphrase", 0.80),
            ("priorities and", 0.79),
            ("semantic search", 0.78),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(["A sample text"], max_tags=5)

    assert [tag.normalized_label for tag in tags] == [
        "machine learning",
        "keyphrase extraction",
        "semantic search",
    ]


def test_keyword_tagger_filters_code_like_noise_tokens() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("document_id category_label", 0.88),
            ("framework selection", 0.84),
            ("api contracts", 0.81),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(["A sample text"], max_tags=5)

    assert [tag.normalized_label for tag in tags] == [
        "framework selection",
        "api contracts",
    ]


def test_keyword_tagger_keeps_english_technical_terms_for_mixed_russian_text() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("vector database", 0.93),
            ("retrieval pipeline", 0.91),
            ("the retrieval", 0.89),
            ("и поиск", 0.88),
            ("векторный поиск", 0.86),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(
        ["В статье обсуждаются vector database и retrieval pipeline для поиска."],
        max_tags=5,
        language_profile=SimpleNamespace(
            dominant_language="ru",
            secondary_language="en",
            mixed_language=True,
            distribution={"ru": 0.56, "en": 0.39, "other": 0.05},
        ),
    )

    assert [tag.normalized_label for tag in tags] == [
        "vector database",
        "retrieval pipeline",
        "векторный поиск",
    ]


def test_keyword_tagger_merges_russian_inflections_by_lemma() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("векторные базы данных", 0.95),
            ("векторных баз данных", 0.91),
            ("поисковые системы", 0.82),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(
        ["Векторные базы данных улучшают качество поиска по документам."],
        max_tags=5,
        language_profile=SimpleNamespace(
            dominant_language="ru",
            secondary_language=None,
            mixed_language=False,
            distribution={"ru": 0.95, "en": 0.05, "other": 0.0},
        ),
    )

    assert [tag.normalized_label for tag in tags] == [
        "векторные базы данных",
        "поисковые системы",
    ]


def test_keyword_tagger_boosts_title_phrases_over_generic_body_terms() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("semantic search", 0.74),
            ("retrieval pipeline", 0.72),
            ("поисковые системы", 0.83),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(
        [
            "Semantic Search в RAG-системах\n\nВ статье рассматриваются поисковые системы и retrieval pipeline."
        ],
        max_tags=3,
        language_profile=SimpleNamespace(
            dominant_language="ru",
            secondary_language="en",
            mixed_language=True,
            distribution={"ru": 0.58, "en": 0.38, "other": 0.04},
        ),
        title_text="Semantic Search в RAG-системах",
    )

    assert [tag.normalized_label for tag in tags][:2] == [
        "semantic search",
        "retrieval pipeline",
    ]


def test_keyword_tagger_merges_mixed_phrases_with_punctuation_variants() -> None:
    extractor = FakeKeywordExtractor(
        [
            ("rag-системы", 0.89),
            ("rag системы", 0.87),
            ("semantic search", 0.84),
        ]
    )
    tagger = KeywordTagger(extractor=extractor)

    tags = tagger.extract_tags(
        ["RAG-системы применяются в semantic search."],
        max_tags=5,
        language_profile=SimpleNamespace(
            dominant_language="ru",
            secondary_language="en",
            mixed_language=True,
            distribution={"ru": 0.51, "en": 0.45, "other": 0.04},
        ),
    )

    assert [tag.normalized_label for tag in tags] == [
        "rag системы",
        "semantic search",
    ]


def test_reconcile_tag_candidates_matches_catalog_aliases_and_localizes_output() -> None:
    catalog = [
        TagCatalogEntry(
            canonical_name="machine learning",
            aliases=["ml", "машинное обучение"],
            labels={
                "ru": "машинное обучение",
                "en": "machine learning",
            },
            category_codes=["technology_ai_ml_nlp_rag"],
        )
    ]

    tags = reconcile_tag_candidates(
        [
            TagCandidate(
                label="ML",
                normalized_label="ml",
                score=0.92,
            )
        ],
        max_tags=5,
        tagging_mode="existing_only",
        existing_tags=catalog,
        output_language="ru",
        category_codes=["technology_ai_ml_nlp_rag"],
    )

    assert len(tags) == 1
    assert tags[0].label == "машинное обучение"
    assert tags[0].normalized_label == "machine learning"
    assert tags[0].canonical_name == "machine learning"
    assert tags[0].method == "catalog_alias_match"


def test_reconcile_tag_candidates_curated_only_drops_unlisted_tags() -> None:
    curated = [
        TagCatalogEntry(
            canonical_name="semantic search",
            aliases=["semantic retrieval"],
            labels={"en": "semantic search"},
            category_codes=["technology_software_retrieval"],
        )
    ]

    tags = reconcile_tag_candidates(
        [
            TagCandidate(
                label="semantic search",
                normalized_label="semantic search",
                score=0.84,
            ),
            TagCandidate(
                label="vector database",
                normalized_label="vector database",
                score=0.81,
            ),
        ],
        max_tags=5,
        tagging_mode="curated_only",
        curated_tags=curated,
        output_language="en",
        category_codes=["technology_software_retrieval"],
    )

    assert [tag.normalized_label for tag in tags] == ["semantic search"]
    assert tags[0].canonical_name == "semantic search"
