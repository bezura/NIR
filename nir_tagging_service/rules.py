from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

from nir_tagging_service.language import LanguageProfile, resolve_output_language
from nir_tagging_service.tag_extraction import TagCandidate


@dataclass(frozen=True, slots=True)
class RuleHints:
    category_boosts: dict[str, float] = field(default_factory=dict)
    tags: list[TagCandidate] = field(default_factory=list)
    matched_rules: list[dict[str, Any]] = field(default_factory=list)


def apply_rule_hints(
    *,
    source: str,
    metadata: Mapping[str, Any] | None,
    title_text: str,
    metadata_terms: list[str],
    language_profile: LanguageProfile,
    output_language: str = "auto",
) -> RuleHints:
    resolved_language = resolve_output_language(output_language, language_profile) or "en"
    category_boosts: dict[str, float] = {}
    tags: list[TagCandidate] = []
    matched_rules: list[dict[str, Any]] = []
    metadata_mapping = metadata or {}
    url_value = _string_value(metadata_mapping, "url", "canonical_url", "source_url")
    domain = _extract_domain(url_value)
    lowered_title = title_text.casefold()
    lowered_terms = {term.casefold() for term in metadata_terms}

    if domain == "arxiv.org":
        _accumulate_boost(category_boosts, "research", 0.18)
        _accumulate_boost(category_boosts, "science_research", 0.22)
        tags.append(
            _rule_tag(
                canonical_name="research paper",
                labels={"ru": "научная статья", "en": "research paper"},
                output_language=resolved_language,
                reason="Matched arXiv domain",
                method="domain_rule",
            )
        )
        matched_rules.append({"rule": "domain:arxiv", "domain": domain})

    if domain == "github.com":
        _accumulate_boost(category_boosts, "technology", 0.15)
        _accumulate_boost(category_boosts, "technology_software_tooling", 0.22)
        tags.append(
            _rule_tag(
                canonical_name="github",
                labels={"ru": "github", "en": "github"},
                output_language=resolved_language,
                reason="Matched GitHub domain",
                method="domain_rule",
            )
        )
        matched_rules.append({"rule": "domain:github", "domain": domain})

    if any(marker in lowered_title for marker in ("benchmark", "evaluation", "error analysis")) or (
        {"benchmark", "evaluation", "precision@k"} & lowered_terms
    ):
        _accumulate_boost(category_boosts, "research_benchmark_evaluation", 0.18)
        tags.append(
            _rule_tag(
                canonical_name="benchmark",
                labels={"ru": "бенчмарк", "en": "benchmark"},
                output_language=resolved_language,
                reason="Matched evaluation-oriented metadata",
                method="metadata_rule",
            )
        )
        matched_rules.append({"rule": "metadata:benchmark"})

    if any(marker in lowered_title for marker in ("readme", "quickstart", "installation", "install")):
        _accumulate_boost(category_boosts, "technology_software_tooling", 0.18)
        tags.append(
            _rule_tag(
                canonical_name="quickstart",
                labels={"ru": "быстрый старт", "en": "quickstart"},
                output_language=resolved_language,
                reason="Matched setup-oriented title",
                method="title_rule",
            )
        )
        matched_rules.append({"rule": "title:quickstart"})

    if source in {"note", "snippet"}:
        _accumulate_boost(category_boosts, "technology_software_tooling", 0.05)

    return RuleHints(
        category_boosts=category_boosts,
        tags=tags,
        matched_rules=matched_rules,
    )


def _accumulate_boost(target: dict[str, float], category_code: str, amount: float) -> None:
    target[category_code] = round(target.get(category_code, 0.0) + amount, 3)


def _rule_tag(
    *,
    canonical_name: str,
    labels: dict[str, str],
    output_language: str,
    reason: str,
    method: str,
) -> TagCandidate:
    label = labels.get(output_language) or labels.get("en") or canonical_name
    return TagCandidate(
        label=label,
        normalized_label=canonical_name,
        score=0.95,
        source="rule",
        method=method,
        confidence=0.95,
        reason=reason,
        canonical_name=canonical_name,
    )


def _string_value(metadata: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_domain(url_value: str) -> str | None:
    if not url_value:
        return None

    parsed = urlparse(url_value)
    domain = parsed.netloc.casefold().strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None
