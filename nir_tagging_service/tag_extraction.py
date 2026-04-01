from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence

from nir_tagging_service.embeddings import SentenceTransformerProvider


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


class KeywordTagger:
    EDGE_STOPWORDS = {
        "a",
        "an",
        "and",
        "at",
        "based",
        "by",
        "compares",
        "document",
        "for",
        "from",
        "in",
        "metadata",
        "new",
        "note",
        "of",
        "on",
        "options",
        "or",
        "paper",
        "path",
        "the",
        "to",
        "using",
        "web_page",
        "with",
        "в",
        "для",
        "и",
        "из",
        "к",
        "на",
        "о",
        "об",
        "по",
        "с",
    }

    def __init__(self, extractor: KeywordExtractionBackend) -> None:
        self.extractor = extractor

    def extract_tags(self, chunks: Sequence[str], max_tags: int = 5) -> list[TagCandidate]:
        joined_text = "\n\n".join(chunk for chunk in chunks if chunk.strip())
        raw_keywords = self.extractor.extract(joined_text, top_n=max_tags * 3)

        deduplicated: dict[str, TagCandidate] = {}

        for keyword, score in raw_keywords:
            normalized = self.normalize_keyword(keyword)
            if not normalized or len(normalized) < 3 or normalized.isdigit():
                continue

            existing = deduplicated.get(normalized)
            candidate = TagCandidate(
                label=normalized,
                normalized_label=normalized,
                score=float(score),
            )

            if existing is None or candidate.score > existing.score:
                deduplicated[normalized] = candidate

        ranked = sorted(deduplicated.values(), key=lambda item: item.score, reverse=True)
        accepted: list[TagCandidate] = []

        for candidate in ranked:
            if self.is_edge_stopword_phrase(candidate.normalized_label):
                continue

            if self.is_code_like_phrase(candidate.normalized_label):
                continue

            if self.is_redundant_substring(candidate.normalized_label, accepted):
                continue

            accepted.append(candidate)
            if len(accepted) >= max_tags:
                break

        return accepted

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        normalized = keyword.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip(".,;:!?()[]{}\"'")
        return normalized

    @classmethod
    def is_edge_stopword_phrase(cls, normalized_keyword: str) -> bool:
        tokens = normalized_keyword.split()
        if not tokens:
            return True

        return tokens[0] in cls.EDGE_STOPWORDS or tokens[-1] in cls.EDGE_STOPWORDS

    @staticmethod
    def is_redundant_substring(normalized_keyword: str, accepted: list[TagCandidate]) -> bool:
        return any(
            normalized_keyword in candidate.normalized_label
            or candidate.normalized_label in normalized_keyword
            for candidate in accepted
            if candidate.normalized_label != normalized_keyword
        )

    @staticmethod
    def is_code_like_phrase(normalized_keyword: str) -> bool:
        return any(marker in normalized_keyword for marker in {"_", "/", "::"})
