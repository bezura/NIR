from __future__ import annotations

import json

from openai import OpenAI


class OpenAICompatibleEnhancer:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        folder_id: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.model = self._normalize_model(model, folder_id)
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url.rstrip("/"),
            timeout=float(timeout_seconds),
            default_headers=self._build_default_headers(folder_id),
        )

    def enhance(
        self,
        text: str,
        category: dict,
        tags: list[dict],
        allowed_tags: list[dict] | None = None,
        output_language: str = "auto",
    ) -> dict:
        allowed_tags_payload = allowed_tags or []
        catalog_instruction = (
            "Select only from the allowed tags list when it is provided. "
            if allowed_tags_payload
            else ""
        )
        prompt = {
            "role": "user",
            "content": (
                "Refine the extracted tags and provide a short explanation for the category. "
                f"{catalog_instruction}"
                f"Prefer the requested output language: {output_language}. "
                "Return strict JSON with keys 'tags' and 'explanation'. "
                "Each item in 'tags' must be an object with keys "
                "'label', 'normalized_label', 'score', 'source', 'method', and optional 'canonical_name'. "
                f"Category: {json.dumps(category, ensure_ascii=False)}\n"
                f"Tags: {json.dumps(tags, ensure_ascii=False)}\n"
                f"Allowed tags: {json.dumps(allowed_tags_payload, ensure_ascii=False)}\n"
                f"Text: {text[:6000]}"
            ),
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                        "role": "system",
                        "content": (
                            "You refine document tags, keep structured provenance, and generate short category explanations."
                        ),
                    },
                prompt,
            ],
        }
        completion = self.client.chat.completions.create(**payload)
        content = completion.choices[0].message.content
        if content is None:
            raise ValueError("llm response content is empty")
        enhanced = json.loads(content)
        return {
            "tags": self._coerce_tags(enhanced.get("tags", tags), tags),
            "explanation": enhanced.get("explanation"),
        }

    @staticmethod
    def _normalize_model(model: str, folder_id: str | None) -> str:
        if model.startswith("gpt://") or not folder_id:
            return model
        return f"gpt://{folder_id}/{model}/latest"

    @staticmethod
    def _build_default_headers(folder_id: str | None) -> dict[str, str] | None:
        if not folder_id:
            return None
        return {"OpenAI-Project": folder_id}

    @staticmethod
    def _coerce_tags(raw_tags: object, fallback_tags: list[dict]) -> list[dict]:
        if not isinstance(raw_tags, list):
            raise TypeError("llm tags must be a list")

        fallback_scores = {
            str(tag.get("normalized_label") or tag.get("label")): float(tag.get("score", 0.0))
            for tag in fallback_tags
        }
        normalized_tags: list[dict] = []

        for raw_tag in raw_tags:
            if isinstance(raw_tag, str):
                normalized_label = raw_tag.strip()
                normalized_tags.append(
                    {
                        "label": normalized_label,
                        "normalized_label": normalized_label,
                        "score": fallback_scores.get(normalized_label, 0.0),
                        "source": "llm",
                        "method": "llm_selected",
                    }
                )
                continue

            if isinstance(raw_tag, dict):
                label = str(raw_tag.get("label") or raw_tag.get("normalized_label") or "").strip()
                if not label:
                    raise TypeError("llm tag object must include label or normalized_label")
                normalized_label = str(raw_tag.get("normalized_label") or label).strip()
                score = float(raw_tag.get("score", fallback_scores.get(normalized_label, 0.0)))
                normalized_tags.append(
                    {
                        "label": label,
                        "normalized_label": normalized_label,
                        "score": score,
                        "source": str(raw_tag.get("source") or "llm"),
                        "method": str(raw_tag.get("method") or "llm_selected"),
                        "canonical_name": raw_tag.get("canonical_name"),
                    }
                )
                continue

            raise TypeError("llm tags must contain strings or objects")

        return normalized_tags
