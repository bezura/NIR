from fastapi.testclient import TestClient


def test_health_endpoint_reports_service_liveness() -> None:
    from nir_tagging_service.app import create_app

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tagging-subsystem",
    }


def test_sqlalchemy_metadata_contains_core_tables() -> None:
    from nir_tagging_service.db.models import Base

    assert {
        "documents",
        "tagging_jobs",
        "tagging_results",
    }.issubset(Base.metadata.tables.keys())


def test_request_schema_captures_text_metadata_and_options() -> None:
    from nir_tagging_service.schemas import CreateTaggingJobRequest

    payload = CreateTaggingJobRequest(
        text="A compact text about transformer embeddings and keyphrase extraction.",
        source="article",
        metadata={"title": "Keyphrase extraction", "language": "en"},
        options={"max_tags": 7, "use_llm_postprocess": False},
    )

    assert payload.text.startswith("A compact text")
    assert payload.source == "article"
    assert payload.metadata["language"] == "en"
    assert payload.options.max_tags == 7


def test_settings_accept_postgresql_database_url() -> None:
    from nir_tagging_service.config import Settings

    settings = Settings(
        database_url="postgresql+psycopg://tagging:tagging@localhost:5432/tagging",
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.api_prefix == "/api/v1/tagging"
