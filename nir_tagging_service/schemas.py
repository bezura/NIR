from typing import Any, Literal

from pydantic import BaseModel, Field


SourceType = Literal["note", "snippet", "web_page", "article", "document"]
TaggingMode = Literal["generate", "existing_only", "curated_only", "hybrid"]
OutputLanguage = Literal["auto", "ru", "en"]
LLMStrategy = Literal["disabled", "low_confidence_only", "always"]
TagSource = Literal["manual", "rule", "model", "llm"]
JobStageStatus = Literal["pending", "in_progress", "completed", "skipped", "failed"]


class TagCatalogEntry(BaseModel):
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)
    category_codes: list[str] = Field(default_factory=list)


class TaggingOptions(BaseModel):
    max_tags: int = Field(default=5, ge=1, le=10)
    use_llm_postprocess: bool = False
    tagging_mode: TaggingMode = "generate"
    output_language: OutputLanguage = "auto"
    enable_rules: bool = True
    llm_strategy: LLMStrategy = "disabled"
    existing_tags: list[TagCatalogEntry] = Field(default_factory=list)
    curated_tags: list[TagCatalogEntry] = Field(default_factory=list)
    content_type_hint: str | None = Field(
        default=None,
        deprecated=True,
        description="Deprecated no-op compatibility field. Currently accepted but not applied.",
    )


class CreateTaggingJobRequest(BaseModel):
    text: str = Field(min_length=1)
    source: SourceType
    metadata: dict[str, Any] = Field(default_factory=dict)
    options: TaggingOptions = Field(default_factory=TaggingOptions)


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    service: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class CreateTaggingJobResponse(BaseModel):
    job_id: str
    status: str
    document_id: str
    status_url: str
    result_url: str


class JobStageResponse(BaseModel):
    name: str
    label: str
    status: JobStageStatus
    started_at: Any | None = None
    finished_at: Any | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    created_at: Any
    started_at: Any | None = None
    finished_at: Any | None = None
    result_available: bool = False
    current_stage: str | None = None
    stage_label: str | None = None
    progress_percent: int = 0
    stage_history: list["JobStageResponse"] = Field(default_factory=list)
    pending_stages: list["JobStageResponse"] = Field(default_factory=list)
    error: ErrorPayload | None = None


class CategoryResponse(BaseModel):
    code: str
    label: str
    score: float


class TagResponse(BaseModel):
    label: str
    normalized_label: str
    score: float
    source: TagSource = "model"
    method: str = "keyword_extractor"
    confidence: float | None = None
    reason: str | None = None
    canonical_name: str | None = None


class JobResultResponse(BaseModel):
    job_id: str
    document_id: str
    category: CategoryResponse
    tags: list[TagResponse]
    score: float
    signals: dict[str, Any]
    explanation: str | None = None
