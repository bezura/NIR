from typing import Any, Literal

from pydantic import BaseModel, Field


SourceType = Literal["note", "snippet", "web_page", "article", "document"]


class TaggingOptions(BaseModel):
    max_tags: int = Field(default=5, ge=1, le=10)
    use_llm_postprocess: bool = False
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


class JobStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    created_at: Any
    started_at: Any | None = None
    finished_at: Any | None = None
    result_available: bool = False
    error: ErrorPayload | None = None


class CategoryResponse(BaseModel):
    code: str
    label: str
    score: float


class TagResponse(BaseModel):
    label: str
    normalized_label: str
    score: float


class JobResultResponse(BaseModel):
    job_id: str
    document_id: str
    category: CategoryResponse
    tags: list[TagResponse]
    score: float
    signals: dict[str, Any]
    explanation: str | None = None
