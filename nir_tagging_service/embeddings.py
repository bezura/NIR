from __future__ import annotations

"""Shared access to the embedding model used by categorization and tagging."""

from pathlib import Path
from typing import Protocol

from sentence_transformers import SentenceTransformer


class SentenceTransformerProvider(Protocol):
    """Minimal provider interface for lazily obtaining a sentence-transformer."""

    def get_model(self) -> SentenceTransformer: ...


class SharedSentenceTransformerProvider:
    """Lazily load and reuse a single sentence-transformer instance."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def get_model(self) -> SentenceTransformer:
        """Return a cached model instance, loading it only on first use."""

        if self._model is None:
            model_name_or_path, local_files_only = resolve_model_name_or_path(self.model_name)
            self._model = SentenceTransformer(
                model_name_or_path,
                local_files_only=local_files_only,
            )

        return self._model


def resolve_model_name_or_path(model_name: str) -> tuple[str, bool]:
    """Prefer a cached Hugging Face snapshot and mark it as local-only."""

    snapshot_root = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / f"models--{model_name.replace('/', '--')}"
        / "snapshots"
    )
    if not snapshot_root.exists():
        return model_name, False

    snapshots = sorted(path for path in snapshot_root.iterdir() if path.is_dir())
    if not snapshots:
        return model_name, False

    return str(snapshots[-1]), True
