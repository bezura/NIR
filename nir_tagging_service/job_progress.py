from __future__ import annotations

"""Helpers for projecting and mutating per-job progress metadata."""

from datetime import datetime, timezone
from typing import Any

from nir_tagging_service.schemas import JobStageResponse, TaggingOptions


STAGE_LABELS = {
    "queued": "В очереди",
    "preprocessing": "Предобработка",
    "rule_hints": "Правила и сигналы",
    "categorization": "Категоризация",
    "tagging": "Тегирование",
    "llm_postprocess": "LLM-уточнение",
    "db_write": "Сохранение результата",
    "completed": "Готово",
}


def initialize_job_progress(options: TaggingOptions, now: datetime) -> dict[str, Any]:
    """Create the initial progress payload for a newly queued job."""

    queued_stage = {
        "name": "queued",
        "label": label_for_stage("queued"),
        "status": "in_progress",
        "started_at": _serialize_datetime(now),
        "finished_at": None,
    }
    return {
        "current_stage": "queued",
        "progress_percent": 0,
        "stage_history": [queued_stage],
        "planned_stages": [name for name, _ in build_stage_plan(options)],
    }


def label_for_stage(stage_name: str | None) -> str | None:
    """Return a localized label for a pipeline stage name."""

    if stage_name is None:
        return None
    return STAGE_LABELS.get(stage_name, stage_name.replace("_", " ").title())


def build_stage_plan(options: TaggingOptions) -> list[tuple[str, str]]:
    """Build the ordered stage list for the selected job options."""

    plan = [
        ("queued", label_for_stage("queued") or "queued"),
        ("preprocessing", label_for_stage("preprocessing") or "preprocessing"),
    ]
    if options.enable_rules:
        plan.append(("rule_hints", label_for_stage("rule_hints") or "rule_hints"))
    plan.extend(
        [
            ("categorization", label_for_stage("categorization") or "categorization"),
            ("tagging", label_for_stage("tagging") or "tagging"),
        ]
    )
    if options.use_llm_postprocess or options.llm_strategy != "disabled":
        plan.append(("llm_postprocess", label_for_stage("llm_postprocess") or "llm_postprocess"))
    plan.extend(
        [
            ("db_write", label_for_stage("db_write") or "db_write"),
            ("completed", label_for_stage("completed") or "completed"),
        ]
    )
    return plan


def start_stage(progress: dict[str, Any], stage_name: str, now: datetime, options: TaggingOptions) -> dict[str, Any]:
    """Mark a stage as currently running."""

    normalized = normalize_progress(progress, options)
    entry = _ensure_entry(normalized, stage_name)
    entry["label"] = label_for_stage(stage_name)
    entry["status"] = "in_progress"
    entry["started_at"] = entry.get("started_at") or _serialize_datetime(now)
    entry["finished_at"] = None
    normalized["current_stage"] = stage_name
    normalized["progress_percent"] = compute_progress_percent(normalized, options)
    return normalized


def complete_stage(progress: dict[str, Any], stage_name: str, now: datetime, options: TaggingOptions) -> dict[str, Any]:
    """Mark a stage as completed and refresh aggregate progress."""

    normalized = normalize_progress(progress, options)
    entry = _ensure_entry(normalized, stage_name)
    entry["label"] = label_for_stage(stage_name)
    entry["status"] = "completed"
    entry["started_at"] = entry.get("started_at") or _serialize_datetime(now)
    entry["finished_at"] = _serialize_datetime(now)
    normalized["current_stage"] = stage_name
    normalized["progress_percent"] = compute_progress_percent(normalized, options)
    return normalized


def skip_stage(progress: dict[str, Any], stage_name: str, now: datetime, options: TaggingOptions) -> dict[str, Any]:
    """Mark an optional stage as skipped."""

    normalized = normalize_progress(progress, options)
    entry = _ensure_entry(normalized, stage_name)
    entry["label"] = label_for_stage(stage_name)
    entry["status"] = "skipped"
    entry["started_at"] = entry.get("started_at") or _serialize_datetime(now)
    entry["finished_at"] = _serialize_datetime(now)
    normalized["progress_percent"] = compute_progress_percent(normalized, options)
    return normalized


def fail_stage(progress: dict[str, Any], stage_name: str, now: datetime, options: TaggingOptions) -> dict[str, Any]:
    """Mark a stage as failed and freeze progress at the failure point."""

    normalized = normalize_progress(progress, options)
    entry = _ensure_entry(normalized, stage_name)
    entry["label"] = label_for_stage(stage_name)
    entry["status"] = "failed"
    entry["started_at"] = entry.get("started_at") or _serialize_datetime(now)
    entry["finished_at"] = _serialize_datetime(now)
    normalized["current_stage"] = stage_name
    normalized["progress_percent"] = compute_progress_percent(normalized, options)
    return normalized


def project_job_progress(
    progress: dict[str, Any] | None,
    options: TaggingOptions,
    overall_status: str,
    *,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Project stored progress into API-ready history and pending stages."""

    if not progress:
        progress = _fallback_progress(options, overall_status, created_at)

    normalized = normalize_progress(progress, options)
    history_models = [JobStageResponse.model_validate(entry) for entry in normalized["stage_history"]]
    history_names = {entry.name for entry in history_models}
    pending_models = [
        JobStageResponse(
            name=name,
            label=label,
            status="pending",
            started_at=None,
            finished_at=None,
        )
        for name, label in build_stage_plan(options)
        if name not in history_names
    ]
    current_stage = normalized.get("current_stage")
    return {
        "current_stage": current_stage,
        "stage_label": label_for_stage(current_stage),
        "progress_percent": int(normalized.get("progress_percent", 0)),
        "stage_history": history_models,
        "pending_stages": pending_models,
    }


def normalize_progress(progress: dict[str, Any] | None, options: TaggingOptions) -> dict[str, Any]:
    """Normalize persisted progress into a stable internal structure."""

    stage_history = []
    if progress:
        stage_history = [dict(entry) for entry in progress.get("stage_history", []) if isinstance(entry, dict)]

    normalized = {
        "current_stage": progress.get("current_stage") if progress else None,
        "progress_percent": int(progress.get("progress_percent", 0)) if progress else 0,
        "stage_history": stage_history,
        "planned_stages": [name for name, _ in build_stage_plan(options)],
    }
    normalized["progress_percent"] = compute_progress_percent(normalized, options)
    return normalized


def compute_progress_percent(progress: dict[str, Any], options: TaggingOptions) -> int:
    """Approximate overall completion percentage from stage history."""

    planned_stages = [name for name, _ in build_stage_plan(options)]
    if not planned_stages:
        return 0

    current_stage = progress.get("current_stage")
    if current_stage == "queued":
        return 0
    if current_stage == "completed":
        return 100

    completed_or_skipped = {
        entry["name"]
        for entry in progress.get("stage_history", [])
        if entry.get("status") in {"completed", "skipped"}
    }
    completed_count = len(completed_or_skipped.intersection(planned_stages))
    in_progress = any(entry.get("status") == "in_progress" for entry in progress.get("stage_history", []))
    progress_units = float(completed_count)
    if in_progress:
        progress_units += 0.5
    percent = int(round((progress_units / len(planned_stages)) * 100))
    return max(0, min(100, percent))


def _ensure_entry(progress: dict[str, Any], stage_name: str) -> dict[str, Any]:
    """Return an existing stage entry or append a pending placeholder."""

    for entry in progress["stage_history"]:
        if entry.get("name") == stage_name:
            return entry

    entry = {
        "name": stage_name,
        "label": label_for_stage(stage_name),
        "status": "pending",
        "started_at": None,
        "finished_at": None,
    }
    progress["stage_history"].append(entry)
    return entry


def _fallback_progress(options: TaggingOptions, overall_status: str, created_at: datetime | None) -> dict[str, Any]:
    """Synthesize a progress payload for legacy rows without stored progress."""

    fallback_now = created_at or datetime.now(timezone.utc)
    if overall_status == "completed":
        progress = initialize_job_progress(options, fallback_now)
        for stage_name, _ in build_stage_plan(options):
            progress = complete_stage(progress, stage_name, fallback_now, options)
        return progress

    if overall_status == "failed":
        progress = initialize_job_progress(options, fallback_now)
        return fail_stage(progress, "queued", fallback_now, options)

    return initialize_job_progress(options, fallback_now)


def _serialize_datetime(value: datetime) -> str:
    """Serialize datetimes in ISO 8601 form for JSON storage."""

    return value.isoformat()
