from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence

from nir_tagging_service.embeddings import SentenceTransformerProvider
from nir_tagging_service.language import LanguageProfile, detect_language_profile, edge_stopwords_for_profile
from nir_tagging_service.schemas import TagCatalogEntry
from nir_tagging_service.tag_postprocessing import (
    RussianLemmatizer,
    build_ranked_candidates,
    is_redundant_candidate,
    normalize_keyword,
)


class KeywordExtractionBackend(Protocol):
    def extract(self, text: str, top_n: int) -> list[tuple[str, float]]: ...


class KeyBERTKeywordExtractor:
    def __init__(self, provider: SentenceTransformerProvider) -> None:
        self.provider = provider
        self._extractor = None

    def _load_extractor(self):
        if self._extractor is None:
            from keybert import KeyBERT

            self._extractor = KeyBERT(model=self.provider.get_model())

        return self._extractor

    def extract(self, text: str, top_n: int) -> list[tuple[str, float]]:
        extractor = self._load_extractor()
        keywords = extractor.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words=None,
            top_n=top_n,
            use_mmr=True,
            diversity=0.4,
        )
        return [(keyword, float(score)) for keyword, score in keywords]


@dataclass(frozen=True, slots=True)
class TagCandidate:
    label: str
    normalized_label: str
    score: float
    source: str = "model"
    method: str = "keyword_extractor"
    confidence: float | None = None
    reason: str | None = None
    canonical_name: str | None = None


def merge_tag_candidates(
    *candidate_groups: Sequence[TagCandidate],
    max_tags: int | None = None,
) -> list[TagCandidate]:
    merged: dict[str, TagCandidate] = {}

    for group in candidate_groups:
        for candidate in group:
            identity = _candidate_identity(candidate)
            existing = merged.get(identity)
            if existing is None or _candidate_rank(candidate) > _candidate_rank(existing):
                merged[identity] = candidate

    results = sorted(merged.values(), key=lambda item: _candidate_rank(item), reverse=True)
    if max_tags is not None:
        return results[:max_tags]
    return results


def reconcile_tag_candidates(
    candidates: Sequence[TagCandidate],
    *,
    max_tags: int,
    tagging_mode: str = "generate",
    existing_tags: Sequence[TagCatalogEntry] | None = None,
    curated_tags: Sequence[TagCatalogEntry] | None = None,
    output_language: str = "auto",
    category_codes: Sequence[str] | None = None,
) -> list[TagCandidate]:
    normalized_category_codes = {code for code in (category_codes or []) if code}
    catalog_entries = _catalog_entries_for_mode(
        tagging_mode=tagging_mode,
        existing_tags=existing_tags or (),
        curated_tags=curated_tags or (),
    )
    resolved: list[TagCandidate] = []

    for candidate in candidates:
        matched_entry, matched_by = _find_catalog_match(
            candidate=candidate,
            catalog_entries=catalog_entries,
            category_codes=normalized_category_codes,
        )
        if matched_entry is not None and matched_by is not None:
            resolved.append(
                _build_catalog_candidate(
                    candidate=candidate,
                    entry=matched_entry,
                    matched_by=matched_by,
                    output_language=output_language,
                    category_codes=normalized_category_codes,
                )
            )
            continue

        if tagging_mode in {"existing_only", "curated_only"}:
            continue

        resolved.append(
            TagCandidate(
                label=candidate.label,
                normalized_label=candidate.normalized_label,
                score=float(candidate.score),
                source=candidate.source,
                method=candidate.method,
                confidence=candidate.confidence if candidate.confidence is not None else float(candidate.score),
                reason=candidate.reason,
                canonical_name=candidate.canonical_name,
            )
        )

    return merge_tag_candidates(resolved, max_tags=max_tags)


def _catalog_entries_for_mode(
    *,
    tagging_mode: str,
    existing_tags: Sequence[TagCatalogEntry],
    curated_tags: Sequence[TagCatalogEntry],
) -> list[TagCatalogEntry]:
    if tagging_mode == "existing_only":
        return list(existing_tags)
    if tagging_mode == "curated_only":
        return list(curated_tags)

    merged: dict[str, TagCatalogEntry] = {}
    for entry in [*curated_tags, *existing_tags]:
        merged.setdefault(normalize_keyword(entry.canonical_name), entry)
    return list(merged.values())


def _find_catalog_match(
    *,
    candidate: TagCandidate,
    catalog_entries: Sequence[TagCatalogEntry],
    category_codes: set[str],
) -> tuple[TagCatalogEntry | None, str | None]:
    best_match: tuple[int, int, TagCatalogEntry, str] | None = None
    candidate_forms = {
        normalize_keyword(candidate.label),
        candidate.normalized_label,
    }
    if candidate.canonical_name:
        candidate_forms.add(normalize_keyword(candidate.canonical_name))

    for entry in catalog_entries:
        canonical = normalize_keyword(entry.canonical_name)
        aliases = {normalize_keyword(alias) for alias in entry.aliases if alias.strip()}
        aliases.update(normalize_keyword(label) for label in entry.labels.values() if label.strip())

        matched_by: str | None = None
        if canonical in candidate_forms:
            matched_by = "catalog_exact_match"
            exactness = 2
        elif candidate_forms & aliases:
            matched_by = "catalog_alias_match"
            exactness = 1
        else:
            continue

        category_match = 1
        if category_codes and entry.category_codes:
            category_match = 1 if category_codes.intersection(entry.category_codes) else 0

        rank = (category_match, exactness)
        if best_match is None or rank > best_match[:2]:
            best_match = (*rank, entry, matched_by)

    if best_match is None:
        return None, None

    return best_match[2], best_match[3]


def _build_catalog_candidate(
    *,
    candidate: TagCandidate,
    entry: TagCatalogEntry,
    matched_by: str,
    output_language: str,
    category_codes: set[str],
) -> TagCandidate:
    canonical_name = entry.canonical_name.strip()
    localized_label = _localized_label(entry, output_language)
    category_bonus = 0.03 if category_codes and set(entry.category_codes).intersection(category_codes) else 0.0

    return TagCandidate(
        label=localized_label,
        normalized_label=normalize_keyword(canonical_name),
        score=min(1.0, float(candidate.score) + category_bonus),
        source=candidate.source,
        method=matched_by,
        confidence=candidate.confidence if candidate.confidence is not None else float(candidate.score),
        reason=candidate.reason or f"Matched catalog entry '{canonical_name}'",
        canonical_name=canonical_name,
    )


def _localized_label(entry: TagCatalogEntry, output_language: str) -> str:
    if output_language in {"ru", "en"}:
        label = entry.labels.get(output_language)
        if label:
            return label

    for language in ("en", "ru"):
        label = entry.labels.get(language)
        if label:
            return label

    return entry.canonical_name


def _candidate_identity(candidate: TagCandidate) -> str:
    if candidate.canonical_name:
        return normalize_keyword(candidate.canonical_name)
    return candidate.normalized_label


def _candidate_rank(candidate: TagCandidate) -> tuple[int, float]:
    source_priority = {
        "manual": 4,
        "rule": 3,
        "llm": 2,
        "model": 1,
    }
    return (
        source_priority.get(candidate.source, 0),
        float(candidate.score),
    )


class KeywordTagger:
    def __init__(self, extractor: KeywordExtractionBackend) -> None:
        self.extractor = extractor
        self.lemmatizer = RussianLemmatizer()

    def extract_tags(
        self,
        chunks: Sequence[str],
        max_tags: int = 5,
        language_profile: LanguageProfile | None = None,
        title_text: str = "",
    ) -> list[TagCandidate]:
        joined_text = "\n\n".join(chunk for chunk in chunks if chunk.strip())
        resolved_language_profile = language_profile or detect_language_profile(joined_text)
        active_edge_stopwords = edge_stopwords_for_profile(resolved_language_profile)
        raw_keywords = self.extractor.extract(joined_text, top_n=max_tags * 3)
        ranked_candidates = build_ranked_candidates(
            raw_keywords=raw_keywords,
            language_profile=resolved_language_profile,
            title_text=title_text,
            lemmatizer=self.lemmatizer,
        )
        accepted: list[object] = []
        results: list[TagCandidate] = []

        for candidate in ranked_candidates:
            if len(candidate.normalized_label) < 3 or candidate.normalized_label.isdigit():
                continue

            if self.is_edge_stopword_phrase(candidate.normalized_label, active_edge_stopwords):
                continue

            if self.is_code_like_phrase(candidate.normalized_label):
                continue

            if is_redundant_candidate(candidate, accepted):
                continue

            accepted.append(candidate)
            results.append(
                TagCandidate(
                    label=candidate.label,
                    normalized_label=candidate.normalized_label,
                    score=float(candidate.score),
                    source="model",
                    method="keyword_extractor",
                    confidence=float(candidate.score),
                )
            )
            if len(results) >= max_tags:
                break

        return results

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        return normalize_keyword(keyword)

    @classmethod
    def is_edge_stopword_phrase(
        cls,
        normalized_keyword: str,
        edge_stopwords: frozenset[str],
    ) -> bool:
        tokens = normalized_keyword.split()
        if not tokens:
            return True

        return tokens[0] in edge_stopwords or tokens[-1] in edge_stopwords

    @staticmethod
    def is_code_like_phrase(normalized_keyword: str) -> bool:
        return any(marker in normalized_keyword for marker in {"_", "/", "::"})
