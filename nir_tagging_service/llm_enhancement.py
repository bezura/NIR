from __future__ import annotations

import json
from urllib import request


class OpenAICompatibleEnhancer:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def enhance(self, text: str, category: dict, tags: list[dict]) -> dict:
        prompt = {
            "role": "user",
            "content": (
                "Refine the extracted tags and provide a short explanation for the category. "
                "Return strict JSON with keys 'tags' and 'explanation'. "
                f"Category: {json.dumps(category, ensure_ascii=False)}\n"
                f"Tags: {json.dumps(tags, ensure_ascii=False)}\n"
                f"Text: {text[:6000]}"
            ),
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You refine document tags and generate short category explanations.",
                },
                prompt,
            ],
        }
        http_request = request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))

        content = raw_payload["choices"][0]["message"]["content"]
        enhanced = json.loads(content)
        return {
            "tags": enhanced.get("tags", tags),
            "explanation": enhanced.get("explanation"),
        }
