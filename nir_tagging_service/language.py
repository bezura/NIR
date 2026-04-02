from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from functools import lru_cache

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )
    import stopwordsiso as stopwordsiso


LANGUAGE_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9+._-]*")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
SUPPORTED_STOPWORD_LANGUAGES = ("en", "ru")

PROJECT_EDGE_STOPWORDS = {
    "article",
    "based",
    "compares",
    "document",
    "documents",
    "metadata",
    "new",
    "note",
    "notes",
    "options",
    "paper",
    "path",
    "snippet",
    "source",
    "web_page",
}


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    dominant_language: str
    secondary_language: str | None
    mixed_language: bool
    distribution: dict[str, float]


def _token_language_weights(token: str) -> tuple[float, float, float]:
    has_cyrillic = bool(CYRILLIC_RE.search(token))
    has_latin = bool(LATIN_RE.search(token))

    if has_cyrillic and has_latin:
        return 0.5, 0.5, 0.0
    if has_cyrillic:
        return 1.0, 0.0, 0.0
    if has_latin:
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def detect_language_profile(text: str) -> LanguageProfile:
    ru_weight = 0.0
    en_weight = 0.0
    other_weight = 0.0

    for token in LANGUAGE_TOKEN_RE.findall(text):
        token_ru, token_en, token_other = _token_language_weights(token)
        ru_weight += token_ru
        en_weight += token_en
        other_weight += token_other

    total = ru_weight + en_weight + other_weight
    if total == 0:
        return LanguageProfile(
            dominant_language="unknown",
            secondary_language=None,
            mixed_language=False,
            distribution={"ru": 0.0, "en": 0.0, "other": 1.0},
        )

    distribution = {
        "ru": round(ru_weight / total, 3),
        "en": round(en_weight / total, 3),
        "other": round(other_weight / total, 3),
    }
    dominant_language = max(distribution, key=distribution.get)
    if dominant_language == "other" and distribution["other"] == 1.0:
        dominant_language = "unknown"

    secondary_candidates = [
        language
        for language in ("ru", "en", "other")
        if language != dominant_language and distribution[language] >= 0.15
    ]
    secondary_language = max(secondary_candidates, key=distribution.get) if secondary_candidates else None

    return LanguageProfile(
        dominant_language=dominant_language,
        secondary_language=secondary_language,
        mixed_language=distribution["ru"] >= 0.15 and distribution["en"] >= 0.15,
        distribution=distribution,
    )


@lru_cache(maxsize=len(SUPPORTED_STOPWORD_LANGUAGES))
def _library_stopwords(language: str) -> frozenset[str]:
    if language not in SUPPORTED_STOPWORD_LANGUAGES:
        return frozenset()
    return frozenset(stopwordsiso.stopwords(language))


def edge_stopwords_for_profile(language_profile: LanguageProfile | None) -> frozenset[str]:
    languages: list[str] = []

    if language_profile is not None:
        if language_profile.dominant_language in SUPPORTED_STOPWORD_LANGUAGES:
            languages.append(language_profile.dominant_language)
        if language_profile.secondary_language in SUPPORTED_STOPWORD_LANGUAGES:
            languages.append(language_profile.secondary_language)

    if not languages:
        languages = list(SUPPORTED_STOPWORD_LANGUAGES)

    combined = set(PROJECT_EDGE_STOPWORDS)
    for language in languages:
        combined.update(_library_stopwords(language))

    return frozenset(combined)
