from nir_tagging_service.preprocessing import (
    LONG_DOCUMENT_THRESHOLD,
    prepare_text,
    select_long_document_categorization_chunks,
)


def test_prepare_text_cleans_short_note_without_chunking() -> None:
    result = prepare_text("  Example \n\n note \t about   NLP  ", source="note")

    assert result.cleaned_text == "Example note about NLP"
    assert result.chunked is False
    assert result.content_type == "note_like"
    assert result.language_profile.dominant_language == "en"
    assert result.language_profile.secondary_language is None
    assert result.language_profile.mixed_language is False
    assert result.categorization_chunks == ["Example note about NLP"]
    assert result.tag_extraction_chunks == ["Example note about NLP"]


def test_prepare_text_chunks_long_document_and_uses_all_chunks_for_categorization() -> None:
    paragraph_a = "Transformer models improve semantic understanding. " * 60
    paragraph_b = "Keyphrase extraction highlights the most relevant concepts. " * 60
    paragraph_c = "Metadata and indexing simplify downstream navigation. " * 60
    text = f"{paragraph_a}\n\n{paragraph_b}\n\n{paragraph_c}"

    assert len(text) > LONG_DOCUMENT_THRESHOLD

    result = prepare_text(text, source="document")

    assert result.chunked is True
    assert result.content_type == "long_document"
    assert len(result.chunks) >= 3
    assert len(result.categorization_chunks) < len(result.tag_extraction_chunks)
    assert result.tag_extraction_chunks == result.chunks
    assert all(len(chunk) <= 1200 for chunk in result.chunks)


def test_prepare_text_detects_russian_document_language() -> None:
    text = "Векторный поиск улучшает качество категоризации и автоматического тегирования документов."

    result = prepare_text(text, source="article")

    assert result.language_profile.dominant_language == "ru"
    assert result.language_profile.secondary_language is None
    assert result.language_profile.mixed_language is False
    assert result.language_profile.distribution["ru"] > 0.9


def test_prepare_text_detects_mixed_language_and_uses_metadata_context() -> None:
    result = prepare_text(
        "В статье сравниваются retrieval pipelines и vector databases для семантического поиска.",
        source="article",
        metadata={
            "title": "Semantic Search в RAG-системах",
            "keywords": ["retrieval", "векторные базы данных"],
        },
    )

    assert result.title_text == "Semantic Search в RAG-системах"
    assert result.metadata_terms == ["retrieval", "векторные базы данных"]
    assert result.language_profile.dominant_language == "ru"
    assert result.language_profile.secondary_language == "en"
    assert result.language_profile.mixed_language is True
    assert result.language_profile.distribution["en"] > 0.15
    assert result.categorization_chunks[0].startswith("Semantic Search в RAG-системах")
    assert "retrieval" in result.tag_extraction_chunks[0]


def test_prepare_text_adds_dedicated_context_chunk_for_long_document_categorization() -> None:
    text = ("Backend architecture observability deployment API contracts retrieval platform. " * 80).strip()

    result = prepare_text(
        text,
        source="document",
        metadata={
            "title": "Architecture of a Multilingual Retrieval Platform",
            "keywords": ["semantic search", "vector database", "retrieval pipeline"],
        },
    )

    assert result.chunked is True
    assert result.content_type == "long_document"
    assert result.categorization_chunks[0] == (
        "Architecture of a Multilingual Retrieval Platform\n"
        "semantic search, vector database, retrieval pipeline"
    )
    assert not result.categorization_chunks[1].startswith("Architecture of a Multilingual Retrieval Platform")
    assert result.tag_extraction_chunks[0].startswith("Architecture of a Multilingual Retrieval Platform")
    assert result.categorization_chunks != result.tag_extraction_chunks


def test_prepare_text_treats_multi_chunk_documents_as_long_documents_even_below_length_threshold() -> None:
    text = (
        ("Architecture decisions for the tagging platform and retrieval system. " * 18)
        + "\n\n"
        + ("Implementation details for workers, queues, and observability. " * 18)
    ).strip()

    assert len(text) < LONG_DOCUMENT_THRESHOLD

    result = prepare_text(
        text,
        source="document",
        metadata={"title": "Platform Architecture Overview"},
    )

    assert result.chunked is True
    assert result.content_type == "long_document"
    assert result.categorization_chunks[0] == "Platform Architecture Overview"


def test_long_document_selector_keeps_informative_middle_chunk() -> None:
    chunks = [
        "Introduction and background for the system design.",
        "General project notes without category evidence.",
        (
            "Semantic search retrieval pipeline vector database reranking embeddings "
            "indexing chunking architecture."
        ),
        "Short appendix with broad remarks.",
        "Conclusion and rollout summary.",
    ]

    selected = select_long_document_categorization_chunks(chunks)

    assert chunks[0] in selected
    assert chunks[-1] in selected
    assert chunks[2] in selected
