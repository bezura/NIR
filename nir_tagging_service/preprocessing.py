from __future__ import annotations

import re
from dataclasses import dataclass


LONG_DOCUMENT_THRESHOLD = 3000
MAX_CHUNK_LENGTH = 1200
MAX_CATEGORIZATION_CHUNKS = 2


@dataclass(slots=True)
class PreparedText:
    cleaned_text: str
    content_type: str
    chunked: bool
    chunks: list[str]
    categorization_chunks: list[str]
    tag_extraction_chunks: list[str]
    categorization_text: str
    tag_extraction_text: str


def normalize_text(text: str) -> str:
    normalized = text.replace("\u00a0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def classify_content_type(source: str, cleaned_text: str) -> str:
    if len(cleaned_text) > LONG_DOCUMENT_THRESHOLD:
        return "long_document"

    if source in {"note", "snippet"}:
        return "note_like"

    return "article_like"


def split_into_chunks(cleaned_text: str) -> list[str]:
    if len(cleaned_text) <= MAX_CHUNK_LENGTH:
        return [cleaned_text]

    chunks: list[str] = []
    start = 0
    text_length = len(cleaned_text)

    while start < text_length:
        end = min(start + MAX_CHUNK_LENGTH, text_length)

        if end < text_length:
            boundary = cleaned_text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = cleaned_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end
        while start < text_length and cleaned_text[start] == " ":
            start += 1

    return chunks or [cleaned_text]


def prepare_text(text: str, source: str) -> PreparedText:
    cleaned_text = normalize_text(text)
    content_type = classify_content_type(source, cleaned_text)
    chunks = split_into_chunks(cleaned_text)
    chunked = len(chunks) > 1
    categorization_chunks = chunks[:MAX_CATEGORIZATION_CHUNKS] if chunked else chunks
    tag_extraction_chunks = chunks

    return PreparedText(
        cleaned_text=cleaned_text,
        content_type=content_type,
        chunked=chunked,
        chunks=chunks,
        categorization_chunks=categorization_chunks,
        tag_extraction_chunks=tag_extraction_chunks,
        categorization_text="\n\n".join(categorization_chunks),
        tag_extraction_text="\n\n".join(tag_extraction_chunks),
    )
