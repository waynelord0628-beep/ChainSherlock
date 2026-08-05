from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from threading import Event, Lock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_investigator.application.execution_errors import ExecutionCancelledError
from crypto_investigator.planner.models import StepType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class ExecutionStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class FailureKind(StrEnum):
    FATAL = "fatal"
    RECOVERABLE = "recoverable"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CANCELLED = "cancelled"


class ArtifactType(StrEnum):
    NORMALIZED_TRANSACTIONS = "normalized_transactions"
    ANALYSIS_RESULT = "analysis_result"
    GRAPH_JSON = "graph_json"
    GRAPHML = "graphml"
    GRAPH_HTML = "graph_html"
    INVESTIGATION_RESULT = "investigation_result"
    OBSERVATIONS = "observations"
    CONCLUSION_FACTS = "conclusion_facts"
    NARRATIVE_RESULT = "narrative_result"
    REPORT_MARKDOWN = "report_markdown"
    REPORT_HTML = "report_html"
    REPORT_DOCX = "report_docx"
    REPORT_PDF = "report_pdf"
    EVIDENCE_MANIFEST = "evidence_manifest"
    PROVIDER_STATUS = "provider_status"
    PROVIDER_ERRORS = "provider_errors"
    REJECTED_RECORDS = "rejected_records"
    EXECUTION_LOG = "execution_log"
    CHECKPOINT = "checkpoint"
    FIRST_HOP_PRODUCT = "first_hop_product"
    FIRST_HOP_CHART_MANIFEST = "first_hop_chart_manifest"
    OTHER = "other"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"


class ExecutionWarning(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    message: str
    step_id: str | None = None


class ExecutionFailure(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: FailureKind
    safe_message: str
    step_id: str | None = None
    retryable: bool = False
    code: str | None = None


class ExecutionArtifact(BaseModel):
    model_config = ConfigDict(extra="allow")
    artifact_id: str = Field(default_factory=lambda: f"artifact_{uuid4().hex}")
    case_id: str
    execution_id: str
    step_id: str
    artifact_type: ArtifactType
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    source: str
    completeness: Completeness = Completeness.COMPLETE
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("artifact timestamp must be timezone-aware")
        return value

    @field_validator("relative_path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("artifact path must be relative and workspace confined")
        return normalized


class ArtifactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_type: ArtifactType
    relative_path: str
    source: str
    completeness: Completeness = Completeness.COMPLETE
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="allow")
    execution_id: str
    step_id: str
    checkpoint_type: str
    created_at: datetime = Field(default_factory=utc_now)
    state: dict[str, Any] = Field(default_factory=dict)
    completed_units: int = Field(default=0, ge=0)
    next_cursor: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    safe_metadata: dict[str, Any] = Field(default_factory=dict)


class StepExecutionResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: ExecutionStepStatus = ExecutionStepStatus.COMPLETED
    artifacts: list[ArtifactCandidate] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
    records_processed: int = Field(default=0, ge=0)
    partial: bool = False
    checkpoint: ExecutionCheckpoint | None = None
    safe_details: dict[str, Any] = Field(default_factory=dict)


class StepExecution(BaseModel):
    model_config = ConfigDict(extra="allow")
    step_id: str
    step_type: StepType
    order: int
    status: ExecutionStepStatus = ExecutionStepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
    failure: ExecutionFailure | None = None
    retry_count: int = Field(default=0, ge=0)
    checkpoint: ExecutionCheckpoint | None = None
    records_processed: int = Field(default=0, ge=0)
    provider: str | None = None
    capability: str | None = None
    partial: bool = False
    skipped_reason: str | None = None


class CaseExecution(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    execution_id: str
    case_id: str
    plan_id: str
    plan_version: int
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_step_id: str | None = None
    steps: list[StepExecution] = Field(default_factory=list)
    artifacts: list[ExecutionArtifact] = Field(default_factory=list)
    warnings: list[ExecutionWarning] = Field(default_factory=list)
    failures: list[ExecutionFailure] = Field(default_factory=list)
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    resume_count: int = Field(default=0, ge=0)
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)


class CaseExecutionResult(BaseModel):
    execution: CaseExecution
    artifacts: list[ExecutionArtifact]
    success: bool


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason: str | None = None
        self._cancelled_at: datetime | None = None

    def request_cancel(self, reason: str = "User requested cancellation") -> None:
        with self._lock:
            if not self._event.is_set():
                self._reason = reason
                self._cancelled_at = utc_now()
                self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        return self._reason

    @property
    def cancelled_at(self) -> datetime | None:
        return self._cancelled_at

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise ExecutionCancelledError(self.reason or "Execution cancelled")
