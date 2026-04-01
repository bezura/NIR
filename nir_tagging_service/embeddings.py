from __future__ import annotations

from typing import Protocol

from sentence_transformers import SentenceTransformer


class SentenceTransformerProvider(Protocol):
    def get_model(self) -> SentenceTransformer: ...


class SharedSentenceTransformerProvider:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)

        return self._model
