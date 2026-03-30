from fastapi.testclient import TestClient

from nir_tagging_service.app import PipelineServices, create_app
from nir_tagging_service.category_catalog import CategoryDefinition
from nir_tagging_service.categorization import CategorizationResult
from nir_tagging_service.config import Settings
from nir_tagging_service.db.models import TaggingJob, TaggingResult
from nir_tagging_service.tag_extraction import TagCandidate


class FakeCategorizer:
    def categorize(self, chunks: list[str]) -> CategorizationResult:
        return CategorizationResult(
            category=CategoryDefinition(
                code="technology_software",
                label="Технологии и разработка",
                description="technology",
            ),
            score=0.84,
            similarities={
                "technology_software": 0.84,
                "science_research": 0.41,
            },
        )


class FakeTagger:
    def extract_tags(self, chunks: list[str], max_tags: int = 5) -> list[TagCandidate]:
        return [
            TagCandidate(
                label="semantic search",
                normalized_label="semantic search",
                score=0.77,
            ),
            TagCandidate(
                label="keyphrase extraction",
                normalized_label="keyphrase extraction",
                score=0.71,
            ),
        ]


class FailingCategorizer:
    def categorize(self, chunks: list[str]) -> CategorizationResult:
        raise RuntimeError("classification pipeline exploded")


class FakeEnhancer:
    def enhance(self, text: str, category: dict, tags: list[dict]) -> dict:
        return {
            "tags": [
                {
                    "label": "semantic retrieval",
                    "normalized_label": "semantic retrieval",
                    "score": 0.79,
                },
                *tags,
            ],
            "explanation": "The document focuses on semantic retrieval and tagging infrastructure.",
        }


class MalformedEnhancer:
    def enhance(self, text: str, category: dict, tags: list[dict]) -> dict:
        return {
            "tags": ["bad-shape"],
            "explanation": "Malformed enhancer payload",
        }


def test_submit_job_persists_completed_result_and_status(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": 5},
            },
        )

        assert response.status_code == 202
        payload = response.json()
        job_id = payload["job_id"]

        status_response = client.get(f"/api/v1/tagging/jobs/{job_id}")
        result_response = client.get(f"/api/v1/tagging/jobs/{job_id}/result")

        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"
        assert result_response.status_code == 200
        assert result_response.json()["category"]["code"] == "technology_software"
        assert len(result_response.json()["tags"]) == 2

        with app.state.session_factory() as session:
            assert session.query(TaggingJob).count() == 1
            assert session.query(TaggingResult).count() == 1


def test_failed_pipeline_marks_job_failed_and_persists_error(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-failed.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FailingCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "A text that will fail in the categorization stage.",
                "source": "article",
                "metadata": {},
                "options": {"max_tags": 5},
            },
        )

        job_id = response.json()["job_id"]
        status_response = client.get(f"/api/v1/tagging/jobs/{job_id}")
        result_response = client.get(f"/api/v1/tagging/jobs/{job_id}/result")

        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"
        assert status_response.json()["error"]["code"] == "processing_failed"
        assert "classification pipeline exploded" in status_response.json()["error"]["message"]
        assert result_response.status_code == 409
        assert result_response.json()["error"]["code"] == "processing_failed"


def test_optional_llm_postprocess_can_enrich_result_without_replacing_base_pipeline(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-llm.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
            enhancer=FakeEnhancer(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": 5, "use_llm_postprocess": True},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        assert result_response.status_code == 200
        assert result_response.json()["tags"][0]["normalized_label"] == "semantic retrieval"
        assert (
            result_response.json()["explanation"]
            == "The document focuses on semantic retrieval and tagging infrastructure."
        )


def test_invalid_options_are_rejected_before_job_is_queued(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-invalid.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": "oops", "use_llm_postprocess": "false"},
            },
        )

        assert response.status_code == 422


def test_malformed_enhancer_payload_falls_back_to_base_result(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-malformed-llm.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
            enhancer=MalformedEnhancer(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": 5, "use_llm_postprocess": True},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        assert result_response.status_code == 200
        assert result_response.json()["tags"][0]["normalized_label"] == "semantic search"
        assert result_response.json()["explanation"] is None
        assert result_response.json()["signals"]["llm_postprocess_error"] is True


def test_in_memory_sqlite_uses_same_engine_for_startup_and_requests() -> None:
    settings = Settings(database_url="sqlite:///:memory:")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": 5},
            },
        )

        assert response.status_code == 202
