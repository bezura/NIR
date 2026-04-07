from __future__ import annotations

"""Keyword normalization, ranking and redundancy filtering helpers."""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from pymorphy3 import MorphAnalyzer

from nir_tagging_service.language import LanguageProfile


DASH_RE = re.compile(r"[-‐‑‒–—―]+")
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9+]+")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
RUSSIAN_NOUNISH_POS = {"NOUN", "ADJF", "ADJS"}


@dataclass(frozen=True, slots=True)
class RankedTagCandidate:
    """Tag candidate augmented with normalized merge tokens and ranking score."""

    label: str
    normalized_label: str
    merge_tokens: tuple[str, ...]
    score: float
    ranking_score: float


class RussianLemmatizer:
    """Small wrapper over pymorphy3 with cached token utilities."""

    def __init__(self) -> None:
        self._analyzer = MorphAnalyzer()

    @lru_cache(maxsize=4096)
    def lemmatize_token(self, token: str) -> str:
        """Lemmatize a Cyrillic token and lowercase non-Cyrillic tokens."""

        normalized = token.lower()
        if not CYRILLIC_RE.search(normalized):
            return normalized
        return self._analyzer.parse(normalized)[0].normal_form

    @lru_cache(maxsize=4096)
    def is_nounish_token(self, token: str) -> bool:
        """Return True for noun/adjective-like tokens usable in tag phrases."""

        normalized = token.lower()
        if not CYRILLIC_RE.search(normalized):
            return True
        parsed = self._analyzer.parse(normalized)[0]
        return parsed.tag.POS in RUSSIAN_NOUNISH_POS


def normalize_keyword(keyword: str) -> str:
    """Lowercase and normalize punctuation/whitespace in a raw keyword."""

    normalized = keyword.strip().lower()
    normalized = DASH_RE.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(".,;:!?()[]{}\"'")
    return normalized


def tokenize_keyword(normalized_keyword: str) -> tuple[str, ...]:
    """Split a normalized keyword into alphanumeric tokens."""

    return tuple(TOKEN_RE.findall(normalized_keyword))


def canonicalize_tokens(tokens: Sequence[str], lemmatizer: RussianLemmatizer) -> tuple[str, ...]:
    """Convert tokens into merge-friendly canonical forms."""

    canonical_tokens: list[str] = []
    for token in tokens:
        normalized = token.lower()
        if CYRILLIC_RE.search(normalized):
            canonical_tokens.append(lemmatizer.lemmatize_token(normalized))
        else:
            canonical_tokens.append(normalized)
    return tuple(canonical_tokens)


def _contains_latin(tokens: Sequence[str]) -> bool:
    """Return True when any token contains Latin characters."""

    return any(LATIN_RE.search(token) for token in tokens)


def _title_bonus(
    normalized_label: str,
    tokens: Sequence[str],
    title_text: str,
    lemmatizer: RussianLemmatizer,
) -> float:
    """Boost candidates that are explicitly echoed by the title."""

    if not title_text:
        return 0.0

    normalized_title = normalize_keyword(title_text)
    if not normalized_title:
        return 0.0

    title_tokens = tokenize_keyword(normalized_title)
    title_token_set = set(canonicalize_tokens(title_tokens, lemmatizer))
    candidate_token_set = set(canonicalize_tokens(tokens, lemmatizer))

    if normalized_label and normalized_label in normalized_title:
        return 0.18

    if len(candidate_token_set) >= 2 and candidate_token_set.issubset(title_token_set):
        return 0.12

    return 0.0


def _noun_phrase_bonus(tokens: Sequence[str], lemmatizer: RussianLemmatizer) -> float:
    """Reward multi-token noun-like phrases."""

    if len(tokens) < 2:
        return 0.0
    if all(lemmatizer.is_nounish_token(token) for token in tokens):
        return 0.05
    return 0.0


def _mixed_language_bonus(tokens: Sequence[str], language_profile: LanguageProfile) -> float:
    """Reward Latin-bearing tags when the document is mixed-language."""

    if not language_profile.mixed_language:
        return 0.0
    if _contains_latin(tokens):
        return 0.12
    return 0.0


def build_ranked_candidates(
    raw_keywords: Iterable[tuple[str, float]],
    language_profile: LanguageProfile,
    title_text: str,
    lemmatizer: RussianLemmatizer,
) -> list[RankedTagCandidate]:
    """Normalize raw extractor output and rank merged tag candidates."""

    merged: dict[tuple[str, ...], RankedTagCandidate] = {}

    for keyword, raw_score in raw_keywords:
        normalized_label = normalize_keyword(keyword)
        tokens = tokenize_keyword(normalized_label)
        if not tokens:
            continue

        merge_tokens = canonicalize_tokens(tokens, lemmatizer)
        boosted_score = float(raw_score)
        boosted_score += _title_bonus(normalized_label, tokens, title_text, lemmatizer)
        boosted_score += _mixed_language_bonus(tokens, language_profile)
        boosted_score += _noun_phrase_bonus(tokens, lemmatizer)

        candidate = RankedTagCandidate(
            label=normalized_label,
            normalized_label=normalized_label,
            merge_tokens=merge_tokens,
            score=float(raw_score),
            ranking_score=round(boosted_score, 6),
        )
        existing = merged.get(merge_tokens)
        if existing is None or candidate.ranking_score > existing.ranking_score:
            merged[merge_tokens] = candidate

    return sorted(merged.values(), key=lambda item: item.ranking_score, reverse=True)


def is_redundant_candidate(
    candidate: RankedTagCandidate,
    accepted: Sequence[RankedTagCandidate],
) -> bool:
    """Return True when a candidate substantially overlaps accepted tags."""

    candidate_tokens = set(candidate.merge_tokens)
    if not candidate_tokens:
        return True

    for existing in accepted:
        existing_tokens = set(existing.merge_tokens)
        if candidate.merge_tokens == existing.merge_tokens:
            return True

        overlap = candidate_tokens & existing_tokens
        if not overlap:
            continue

        smaller_size = min(len(candidate_tokens), len(existing_tokens))
        if smaller_size == 0:
            continue

        overlap_ratio = len(overlap) / smaller_size
        if overlap_ratio >= 1.0 and len(candidate_tokens) != len(existing_tokens):
            return True
        if overlap_ratio >= 0.8 and abs(len(candidate_tokens) - len(existing_tokens)) <= 1:
            return True

    return False
