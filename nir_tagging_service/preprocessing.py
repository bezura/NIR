from __future__ import annotations

"""Text normalization and chunk preparation for downstream pipeline stages."""

import re
from dataclasses import dataclass
from typing import Any, Mapping

from nir_tagging_service.language import LanguageProfile, detect_language_profile


LONG_DOCUMENT_THRESHOLD = 3000
MAX_CHUNK_LENGTH = 1200
INFORMATIVE_CHUNK_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_-]{3,}")
SECTION_MARKERS = (
    "abstract",
    "introduction",
    "overview",
    "background",
    "implementation",
    "architecture",
    "results",
    "discussion",
    "summary",
    "conclusion",
    "заключение",
    "выводы",
    "итоги",
    "введение",
    "обзор",
    "архитектура",
    "результаты",
    "обсуждение",
)


@dataclass(slots=True)
class PreparedText:
    """Prepared text plus derived metadata reused across pipeline stages."""

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
    """Normalize whitespace and non-breaking spaces in user-provided text."""

    normalized = text.replace("\u00a0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_title_text(metadata: Mapping[str, Any] | None) -> str:
    """Extract a human-readable title from supported metadata keys."""

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
    """Extract and deduplicate short metadata terms used as lightweight context."""

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
    """Build the contextual prefix prepended to categorization and tagging chunks."""

    parts: list[str] = []

    if title_text:
        parts.append(title_text)
    if metadata_terms:
        parts.append(", ".join(metadata_terms))

    return "\n".join(parts)


def attach_context_to_chunks(chunks: list[str], context_prefix: str) -> list[str]:
    """Attach context only to the first chunk to avoid repeating metadata everywhere."""

    if not chunks:
        return [context_prefix] if context_prefix else []
    if not context_prefix:
        return list(chunks)

    contextualized = list(chunks)
    contextualized[0] = f"{context_prefix}\n\n{contextualized[0]}"
    return contextualized


def _term_density(text: str) -> float:
    """Estimate how terminology-dense a chunk is for evidence selection."""

    all_tokens = [token.casefold() for token in INFORMATIVE_CHUNK_TOKEN_RE.findall(text)]
    if not all_tokens:
        return 0.0

    dense_tokens = [
        token for token in all_tokens
        if len(token) >= 7 or "-" in token or "_" in token
    ]
    if not dense_tokens:
        return 0.0

    return len(set(dense_tokens)) / len(all_tokens)


def _chunk_priority(chunk: str) -> float:
    """Score a chunk for long-document categorization evidence selection."""

    lowered = chunk.casefold()
    score = _term_density(chunk)

    if any(marker in lowered for marker in SECTION_MARKERS):
        score += 0.35

    return round(score, 6)


def select_long_document_categorization_chunks(chunks: list[str]) -> list[str]:
    """Select a compact long-document view for categorization."""

    if len(chunks) <= 4:
        return list(chunks)

    selected_indices = {0, len(chunks) - 1}
    middle_indices = list(range(1, len(chunks) - 1))
    ranked_middle_indices = sorted(
        middle_indices,
        key=lambda index: (_chunk_priority(chunks[index]), -index),
        reverse=True,
    )
    selected_indices.update(ranked_middle_indices[:2])

    deduped: list[str] = []
    seen: set[str] = set()
    for index in sorted(selected_indices):
        chunk = chunks[index]
        key = chunk.casefold()
        if key in seen:
            continue
        deduped.append(chunk)
        seen.add(key)

    return deduped


def build_categorization_chunks(chunks: list[str], context_prefix: str, content_type: str) -> list[str]:
    """Build the chunk sequence that is scored during categorization."""

    if content_type == "long_document":
        base_chunks = select_long_document_categorization_chunks(chunks)
        if not context_prefix:
            return base_chunks
        return [context_prefix, *base_chunks]

    return attach_context_to_chunks(list(chunks), context_prefix)


def classify_content_type(source: str, cleaned_text: str, chunk_count: int) -> str:
    """Classify the content into a lightweight processing mode."""

    if source == "document" and chunk_count > 1:
        return "long_document"

    if len(cleaned_text) > LONG_DOCUMENT_THRESHOLD:
        return "long_document"

    if source in {"note", "snippet"}:
        return "note_like"

    return "article_like"


def split_into_chunks(cleaned_text: str) -> list[str]:
    """Split long text into whitespace-aligned chunks of bounded size."""

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
    """Produce the normalized text representation shared by all pipeline stages."""

    cleaned_text = normalize_text(text)
    title_text = extract_title_text(metadata)
    metadata_terms = extract_metadata_terms(metadata)
    context_prefix = build_context_prefix(title_text, metadata_terms)
    language_input = " ".join(part for part in [title_text, *metadata_terms, cleaned_text] if part)
    language_profile = detect_language_profile(language_input)
    chunks = split_into_chunks(cleaned_text)
    content_type = classify_content_type(source, cleaned_text, len(chunks))
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
