from nir_tagging_service.preprocessing import LONG_DOCUMENT_THRESHOLD, prepare_text


def test_prepare_text_cleans_short_note_without_chunking() -> None:
    result = prepare_text("  Example \n\n note \t about   NLP  ", source="note")

    assert result.cleaned_text == "Example note about NLP"
    assert result.chunked is False
    assert result.content_type == "note_like"
    assert result.categorization_chunks == ["Example note about NLP"]
    assert result.tag_extraction_chunks == ["Example note about NLP"]


def test_prepare_text_chunks_long_document_and_uses_subset_for_categorization() -> None:
    paragraph_a = "Transformer models improve semantic understanding. " * 60
    paragraph_b = "Keyphrase extraction highlights the most relevant concepts. " * 60
    paragraph_c = "Metadata and indexing simplify downstream navigation. " * 60
    text = f"{paragraph_a}\n\n{paragraph_b}\n\n{paragraph_c}"

    assert len(text) > LONG_DOCUMENT_THRESHOLD

    result = prepare_text(text, source="document")

    assert result.chunked is True
    assert result.content_type == "long_document"
    assert len(result.chunks) >= 3
    assert result.categorization_chunks == result.chunks[:2]
    assert result.tag_extraction_chunks == result.chunks
    assert len(result.categorization_text) < len(result.tag_extraction_text)
    assert all(len(chunk) <= 1200 for chunk in result.chunks)
