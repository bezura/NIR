import numpy as np


class FakeSentenceTransformer:
    init_count = 0

    def __init__(self, model_name: str) -> None:
        type(self).init_count += 1
        self.model_name = model_name

    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 2), dtype=float)


class FakeProvider:
    def __init__(self, model: object) -> None:
        self.model = model
        self.get_model_calls = 0

    def get_model(self) -> object:
        self.get_model_calls += 1
        return self.model


def test_shared_embedding_provider_loads_sentence_transformer_once(monkeypatch) -> None:
    from nir_tagging_service.embeddings import SharedSentenceTransformerProvider

    FakeSentenceTransformer.init_count = 0
    monkeypatch.setattr(
        "nir_tagging_service.embeddings.SentenceTransformer",
        FakeSentenceTransformer,
    )

    provider = SharedSentenceTransformerProvider("demo-model")

    assert provider.get_model() is provider.get_model()
    assert FakeSentenceTransformer.init_count == 1


def test_keybert_extractor_reuses_provider_model(monkeypatch) -> None:
    from nir_tagging_service.tag_extraction import KeyBERTKeywordExtractor

    class FakeKeyBERT:
        def __init__(self, model: object) -> None:
            self.model = model

        def extract_keywords(self, text: str, **kwargs) -> list[tuple[str, float]]:
            return [("semantic search", 0.88)]

    shared_model = object()
    provider = FakeProvider(shared_model)
    monkeypatch.setattr("keybert.KeyBERT", FakeKeyBERT)

    extractor = KeyBERTKeywordExtractor(provider)

    assert extractor.extract("Semantic retrieval pipeline", top_n=3) == [
        ("semantic search", 0.88)
    ]
    assert provider.get_model_calls == 1
