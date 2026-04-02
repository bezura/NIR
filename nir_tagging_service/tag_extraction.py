from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, Sequence

from nir_tagging_service.embeddings import SentenceTransformerProvider
from nir_tagging_service.language import LanguageProfile, detect_language_profile, edge_stopwords_for_profile
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
