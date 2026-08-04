from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from crypto_investigator.application.execution_models import utc_now


class EventType(StrEnum):
    EXECUTION_STARTED = "execution_started"
    STEP_STARTED = "step_started"
    PROGRESS = "progress"
    RECORDS_UPDATED = "records_updated"
    WARNING = "warning"
    ARTIFACT_CREATED = "artifact_created"
    CHECKPOINT_SAVED = "checkpoint_saved"
    STEP_COMPLETED = "step_completed"
    STEP_PARTIAL = "step_partial"
    STEP_FAILED = "step_failed"
    STEP_CANCELLED = "step_cancelled"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_PARTIAL = "execution_partial"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    EXECUTION_SUSPENDED = "execution_suspended"
    EXECUTION_RESUMED = "execution_resumed"


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    execution_id: str
    case_id: str
    step_id: str | None = None
    event_type: EventType
    stage: str
    status: str
    message: str
    occurred_at: datetime = Field(default_factory=utc_now)
    elapsed_seconds: float | None = None
    current_records: int = 0
    total_records_if_known: int | None = None
    provider: str | None = None
    capability: str | None = None
    warnings_count: int = 0
    rejected_count: int = 0
    artifacts: list[str] = Field(default_factory=list)
    safe_details: dict[str, Any] = Field(default_factory=dict)
