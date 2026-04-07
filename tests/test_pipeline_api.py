import asyncio
import warnings

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nir_tagging_service.app import create_app
from nir_tagging_service.bootstrap import PipelineServices
from nir_tagging_service.category_catalog import CategoryDefinition
from nir_tagging_service.categorization import CategorizationResult
from nir_tagging_service.config import Settings
from nir_tagging_service.db.models import TaggingJob, TaggingResult
from nir_tagging_service.tag_extraction import TagCandidate


async def _count_rows(app, model) -> int:
    async with app.state.session_factory() as session:
        statement = select(func.count()).select_from(model)
        return await session.scalar(statement)


class FakeCategorizer:
    def categorize(self, chunks: list[str], score_boosts: dict[str, float] | None = None) -> CategorizationResult:
        domain = CategoryDefinition(
            code="technology",
            label="Технологии",
            description="technology",
        )
        leaf = CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        )
        return CategorizationResult(
            category=leaf,
            score=0.84,
            similarities={
                "technology_software": 0.84,
                "science_research": 0.41,
            },
            category_path=[domain, leaf],
            category_depth=2,
            category_is_leaf=True,
            classification_trace=[
                {
                    "depth": 1,
                    "selected_code": "technology",
                    "top_1_score": 0.88,
                    "top_2_score": 0.36,
                    "confidence_gap": 0.52,
                    "accepted": True,
                },
                {
                    "depth": 2,
                    "selected_code": "technology_software",
                    "top_1_score": 0.84,
                    "top_2_score": 0.41,
                    "confidence_gap": 0.43,
                    "accepted": True,
                },
            ],
        )


class FakeTagger:
    def extract_tags(
        self,
        chunks: list[str],
        max_tags: int = 5,
        language_profile=None,
        title_text: str = "",
    ) -> list[TagCandidate]:
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
    def categorize(self, chunks: list[str], score_boosts: dict[str, float] | None = None) -> CategorizationResult:
        raise RuntimeError("classification pipeline exploded")


class FakeLowConfidenceCategorizer:
    def categorize(self, chunks: list[str], score_boosts: dict[str, float] | None = None) -> CategorizationResult:
        domain = CategoryDefinition(
            code="technology",
            label="Технологии",
            description="technology",
        )
        branch = CategoryDefinition(
            code="technology_software",
            label="Технологии и разработка",
            description="technology",
        )
        return CategorizationResult(
            category=branch,
            score=0.58,
            similarities={
                "technology_software": 0.58,
                "science_research": 0.55,
                "education_learning": 0.24,
            },
            top_1_score=0.58,
            top_2_score=0.55,
            confidence_gap=0.03,
            low_confidence=True,
            low_confidence_reasons=["small_gap", "taxonomy_gap", "stopped_before_leaf"],
            num_chunks_scored=5,
            informative_chunk_indices=[0, 4],
            category_path=[domain, branch],
            category_depth=2,
            category_is_leaf=False,
            classification_trace=[
                {
                    "depth": 1,
                    "selected_code": "technology",
                    "top_1_score": 0.81,
                    "top_2_score": 0.33,
                    "confidence_gap": 0.48,
                    "accepted": True,
                },
                {
                    "depth": 2,
                    "selected_code": "technology_software_backend",
                    "top_1_score": 0.58,
                    "top_2_score": 0.55,
                    "confidence_gap": 0.03,
                    "accepted": False,
                },
            ],
        )


class FakeEnhancer:
    def enhance(
        self,
        text: str,
        category: dict,
        tags: list[dict],
        allowed_tags: list[dict] | None = None,
        output_language: str = "auto",
    ) -> dict:
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
    def enhance(
        self,
        text: str,
        category: dict,
        tags: list[dict],
        allowed_tags: list[dict] | None = None,
        output_language: str = "auto",
    ) -> dict:
        return {
            "tags": ["bad-shape"],
            "explanation": "Malformed enhancer payload",
        }


class FakeRuleAwareCategorizer:
    def __init__(self) -> None:
        self.last_score_boosts: dict[str, float] = {}

    def categorize(self, chunks: list[str], score_boosts: dict[str, float] | None = None) -> CategorizationResult:
        self.last_score_boosts = dict(score_boosts or {})

        if self.last_score_boosts.get("science_research", 0.0) > 0:
            domain = CategoryDefinition(
                code="research",
                label="Исследования",
                description="research",
            )
            leaf = CategoryDefinition(
                code="science_research",
                label="Наука и исследования",
                description="research",
            )
            return CategorizationResult(
                category=leaf,
                score=0.89,
                similarities={
                    "science_research": 0.89,
                    "technology_software": 0.51,
                },
                category_path=[domain, leaf],
                category_depth=2,
                category_is_leaf=True,
                classification_trace=[
                    {
                        "depth": 1,
                        "selected_code": "research",
                        "top_1_score": 0.9,
                        "top_2_score": 0.55,
                        "confidence_gap": 0.35,
                        "accepted": True,
                    },
                    {
                        "depth": 2,
                        "selected_code": "science_research",
                        "top_1_score": 0.89,
                        "top_2_score": 0.51,
                        "confidence_gap": 0.38,
                        "accepted": True,
                    },
                ],
            )

        return FakeCategorizer().categorize(chunks, score_boosts=score_boosts)


class CountingEnhancer:
    def __init__(self) -> None:
        self.calls = 0

    def enhance(
        self,
        text: str,
        category: dict,
        tags: list[dict],
        allowed_tags: list[dict] | None = None,
        output_language: str = "auto",
    ) -> dict:
        self.calls += 1
        return {
            "tags": tags,
            "explanation": f"Enhanced in {output_language}",
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
        assert status_response.json()["current_stage"] == "completed"
        assert status_response.json()["stage_label"] == "Готово"
        assert status_response.json()["progress_percent"] == 100
        assert [stage["name"] for stage in status_response.json()["stage_history"]] == [
            "queued",
            "preprocessing",
            "rule_hints",
            "categorization",
            "tagging",
            "db_write",
            "completed",
        ]
        assert status_response.json()["pending_stages"] == []
        assert result_response.status_code == 200
        assert result_response.json()["category"]["code"] == "technology_software"
        assert len(result_response.json()["tags"]) == 2

        assert asyncio.run(_count_rows(app, TaggingJob)) == 1
        assert asyncio.run(_count_rows(app, TaggingResult)) == 1


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
        assert status_response.json()["current_stage"] == "categorization"
        assert status_response.json()["stage_label"] == "Категоризация"
        assert status_response.json()["progress_percent"] > 0
        assert status_response.json()["stage_history"][-1]["name"] == "categorization"
        assert status_response.json()["stage_history"][-1]["status"] == "failed"
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


def test_result_response_exposes_standardized_diagnostics(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-diagnostics.db'}")
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
                "options": {"max_tags": 5, "content_type_hint": "article_like"},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        assert result_response.status_code == 200
        signals = result_response.json()["signals"]
        assert signals["content_type"] == "article_like"
        assert signals["chunked"] is False
        assert signals["num_chunks"] == 1
        assert signals["pipeline"]["content_type_hint"] == "article_like"
        assert signals["pipeline"]["content_type_hint_applied"] is False
        assert "timings_ms" in signals
        assert "category_scores_top_k" in signals


def test_deprecated_content_type_hint_remains_runtime_safe(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-deprecated-hint.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/tagging/jobs",
                json={
                    "text": "Transformer embeddings improve search quality and explainability.",
                    "source": "article",
                    "metadata": {"title": "Embeddings"},
                    "options": {"max_tags": 5, "content_type_hint": "article_like"},
                },
            )

            result_response = client.get(
                f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
            )

        assert response.status_code == 202
        assert result_response.status_code == 200
        assert result_response.json()["signals"]["pipeline"]["content_type_hint"] == "article_like"
        assert not [warning for warning in captured if issubclass(warning.category, DeprecationWarning)]


def test_result_response_exposes_language_signals_for_mixed_text(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-language.db'}")
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
                "text": "В статье сравниваются retrieval pipelines и vector databases для семантического поиска.",
                "source": "article",
                "metadata": {
                    "title": "Semantic Search в RAG-системах",
                    "keywords": ["retrieval", "векторные базы данных"],
                },
                "options": {"max_tags": 5},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        language = result_response.json()["signals"]["language"]
        assert language["dominant"] == "ru"
        assert language["secondary"] == "en"
        assert language["mixed"] is True
        assert language["distribution"]["en"] > 0.15


def test_result_response_reports_top_k_scores_in_descending_order(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-scores.db'}")
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
                "metadata": {},
                "options": {"max_tags": 5},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        top_k = result_response.json()["signals"]["category_scores_top_k"]
        assert top_k[0]["code"] == "technology_software"
        assert top_k[0]["score"] >= top_k[1]["score"]


def test_result_response_persists_stage_timings(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-timings.db'}")
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
                "metadata": {},
                "options": {"max_tags": 5},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        timings = result_response.json()["signals"]["timings_ms"]
        assert {"preprocessing", "categorization", "tagging", "db_write", "total"} <= set(timings)
        assert all(timings[key] >= 0 for key in timings)


def test_result_response_marks_low_confidence_classification_in_signals(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-low-confidence.db'}")
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeLowConfidenceCategorizer(),
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Документ смешивает исследовательское описание, архитектуру сервиса и benchmarking details.",
                "source": "document",
                "metadata": {"title": "Hybrid research and platform overview"},
                "options": {"max_tags": 5},
            },
        )

        result_response = client.get(
            f"/api/v1/tagging/jobs/{response.json()['job_id']}/result"
        )

        classification = result_response.json()["signals"]["classification"]
        assert classification["low_confidence"] is True
        assert classification["confidence_gap"] == 0.03
        assert classification["num_chunks_scored"] == 5
        assert classification["informative_chunk_indices"] == [0, 4]
        assert "taxonomy_gap" in classification["low_confidence_reasons"]
        assert classification["category_depth"] == 2
        assert classification["category_is_leaf"] is False
        assert [node["code"] for node in classification["category_path"]] == [
            "technology",
            "technology_software",
        ]
        assert classification["classification_trace"][-1]["accepted"] is False


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


def test_pipeline_applies_rule_hints_and_catalog_reconciliation(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-rules.db'}")
    categorizer = FakeRuleAwareCategorizer()
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=categorizer,
            tagger=FakeTagger(),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "This paper evaluates multilingual tagging systems and benchmark quality.",
                "source": "article",
                "metadata": {
                    "title": "A Benchmark Study",
                    "url": "https://arxiv.org/abs/2401.12345",
                },
                "options": {
                    "max_tags": 5,
                    "enable_rules": True,
                    "tagging_mode": "existing_only",
                    "output_language": "ru",
                    "existing_tags": [
                        {
                            "canonical_name": "research paper",
                            "aliases": ["paper", "научная статья"],
                            "labels": {
                                "ru": "научная статья",
                                "en": "research paper",
                            },
                            "category_codes": ["science_research"],
                        }
                    ],
                },
            },
        )

        result_response = client.get(f"/api/v1/tagging/jobs/{response.json()['job_id']}/result")

        assert result_response.status_code == 200
        payload = result_response.json()
        assert payload["category"]["code"] == "science_research"
        assert payload["tags"][0]["label"] == "научная статья"
        assert payload["tags"][0]["normalized_label"] == "research paper"
        assert payload["tags"][0]["canonical_name"] == "research paper"
        assert payload["tags"][0]["source"] == "rule"
        assert payload["signals"]["rule_hints"]["matched_rules"][0]["rule"] == "domain:arxiv"
        assert payload["signals"]["pipeline"]["tagging_mode"] == "existing_only"
        assert payload["signals"]["pipeline"]["output_language"] == "ru"
        assert categorizer.last_score_boosts["science_research"] > 0


def test_low_confidence_llm_strategy_runs_enhancer_only_for_ambiguous_results(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-llm-strategy.db'}")
    enhancer = CountingEnhancer()
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeLowConfidenceCategorizer(),
            tagger=FakeTagger(),
            enhancer=enhancer,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Документ смешивает исследовательское описание, архитектуру сервиса и benchmarking details.",
                "source": "document",
                "metadata": {"title": "Hybrid research and platform overview"},
                "options": {"max_tags": 5, "llm_strategy": "low_confidence_only"},
            },
        )

        result_response = client.get(f"/api/v1/tagging/jobs/{response.json()['job_id']}/result")
        status_response = client.get(f"/api/v1/tagging/jobs/{response.json()['job_id']}")

        assert result_response.status_code == 200
        assert enhancer.calls == 1
        assert result_response.json()["signals"]["llm_postprocessed"] is True
        assert any(
            stage["name"] == "llm_postprocess" and stage["status"] == "completed"
            for stage in status_response.json()["stage_history"]
        )


def test_high_confidence_result_skips_low_confidence_llm_strategy(tmp_path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-no-llm.db'}")
    enhancer = CountingEnhancer()
    app = create_app(
        settings=settings,
        pipeline_services=PipelineServices(
            categorizer=FakeCategorizer(),
            tagger=FakeTagger(),
            enhancer=enhancer,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/tagging/jobs",
            json={
                "text": "Transformer embeddings improve search quality and explainability.",
                "source": "article",
                "metadata": {"title": "Embeddings"},
                "options": {"max_tags": 5, "llm_strategy": "low_confidence_only"},
            },
        )

        result_response = client.get(f"/api/v1/tagging/jobs/{response.json()['job_id']}/result")
        status_response = client.get(f"/api/v1/tagging/jobs/{response.json()['job_id']}")

        assert result_response.status_code == 200
        assert enhancer.calls == 0
        assert result_response.json()["signals"]["llm_postprocessed"] is False
        assert any(
            stage["name"] == "llm_postprocess" and stage["status"] == "skipped"
            for stage in status_response.json()["stage_history"]
        )
