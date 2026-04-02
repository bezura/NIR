from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from nir_tagging_service.language import LanguageProfile, detect_language_profile


LONG_DOCUMENT_THRESHOLD = 3000
MAX_CHUNK_LENGTH = 1200


@dataclass(slots=True)
class PreparedText:
    cleaned_text: str
    title_text: str
    metadata_terms: list[str]
    context_prefix: str
    language_profile: LanguageProfile
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


def extract_title_text(metadata: Mapping[str, Any] | None) -> str:
    if not metadata:
        return ""

    for key in ("title", "headline", "subject"):
        value = metadata.get(key)
        if isinstance(value, str):
            normalized = normalize_text(value)
            if normalized:
                return normalized

    return ""


def extract_metadata_terms(metadata: Mapping[str, Any] | None) -> list[str]:
    if not metadata:
        return []

    raw_terms: list[str] = []
    for key in ("keywords", "tags", "topics"):
        value = metadata.get(key)
        if isinstance(value, str):
            raw_terms.append(value)
        elif isinstance(value, list):
            raw_terms.extend(str(item) for item in value if item is not None)

    normalized_terms: list[str] = []
    seen_terms: set[str] = set()

    for term in raw_terms:
        normalized = normalize_text(term)
        if not normalized:
            continue
        dedupe_key = normalized.casefold()
        if dedupe_key in seen_terms:
            continue
        normalized_terms.append(normalized)
        seen_terms.add(dedupe_key)

    return normalized_terms[:5]


def build_context_prefix(title_text: str, metadata_terms: list[str]) -> str:
    parts: list[str] = []

    if title_text:
        parts.append(title_text)
    if metadata_terms:
        parts.append(", ".join(metadata_terms))

    return "\n".join(parts)


def attach_context_to_chunks(chunks: list[str], context_prefix: str) -> list[str]:
    if not chunks:
        return [context_prefix] if context_prefix else []
    if not context_prefix:
        return list(chunks)

    contextualized = list(chunks)
    contextualized[0] = f"{context_prefix}\n\n{contextualized[0]}"
    return contextualized


def select_long_document_categorization_chunks(chunks: list[str]) -> list[str]:
    if len(chunks) <= 3:
        return list(chunks)

    selected = [chunks[0], chunks[1], chunks[-1]]
    deduped: list[str] = []
    seen: set[str] = set()

    for chunk in selected:
        key = chunk.casefold()
        if key in seen:
            continue
        deduped.append(chunk)
        seen.add(key)

    return deduped


def build_categorization_chunks(chunks: list[str], context_prefix: str, content_type: str) -> list[str]:
    base_chunks = list(chunks)
    if content_type == "long_document":
        base_chunks = select_long_document_categorization_chunks(chunks)
    contextualized = attach_context_to_chunks(base_chunks, context_prefix)
    if not context_prefix:
        return contextualized
    if content_type != "long_document":
        return contextualized
    return [context_prefix, *contextualized]


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


def prepare_text(
    text: str,
    source: str,
    metadata: Mapping[str, Any] | None = None,
) -> PreparedText:
    cleaned_text = normalize_text(text)
    title_text = extract_title_text(metadata)
    metadata_terms = extract_metadata_terms(metadata)
    context_prefix = build_context_prefix(title_text, metadata_terms)
    language_input = " ".join(part for part in [title_text, *metadata_terms, cleaned_text] if part)
    language_profile = detect_language_profile(language_input)
    content_type = classify_content_type(source, cleaned_text)
    chunks = split_into_chunks(cleaned_text)
    chunked = len(chunks) > 1
    categorization_chunks = build_categorization_chunks(chunks, context_prefix, content_type)
    tag_extraction_chunks = attach_context_to_chunks(chunks, context_prefix)

    return PreparedText(
        cleaned_text=cleaned_text,
        title_text=title_text,
        metadata_terms=metadata_terms,
        context_prefix=context_prefix,
        language_profile=language_profile,
        content_type=content_type,
        chunked=chunked,
        chunks=chunks,
        categorization_chunks=categorization_chunks,
        tag_extraction_chunks=tag_extraction_chunks,
        categorization_text="\n\n".join(categorization_chunks),
        tag_extraction_text="\n\n".join(tag_extraction_chunks),
    )
