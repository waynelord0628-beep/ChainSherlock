from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.planner.goals import InvestigationGoal


class PlannerType(StrEnum):
    DETERMINISTIC = "deterministic"
    AI_DRAFT = "ai_draft"


class StepType(StrEnum):
    VALIDATE_CASE_INPUTS = "validate_case_inputs"
    PARSE_STRUCTURED_ATTACHMENT = "parse_structured_attachment"
    IMPORT_TRANSACTIONS = "import_transactions"
    DETECT_CHAIN = "detect_chain"
    ANALYZE_ADDRESS = "analyze_address"
    ANALYZE_TRANSACTION = "analyze_transaction"
    COMPARE_KNOWN_ADDRESSES = "compare_known_addresses"
    MATCH_VICTIM_TRANSACTIONS = "match_victim_transactions"
    BUILD_GRAPH = "build_graph"
    RUN_INVESTIGATION_FEATURES = "run_investigation_features"
    APPLY_LOCAL_LABELS = "apply_local_labels"
    GENERATE_NARRATIVE = "generate_narrative"
    GENERATE_REPORT = "generate_report"
    EXPORT_EVIDENCE_MANIFEST = "export_evidence_manifest"
    REQUEST_MANUAL_REVIEW = "request_manual_review"
    UNSUPPORTED_RECOMMENDED_STEP = "unsupported_recommended_step"


class StepStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    SKIPPED = "skipped"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WarningKind(StrEnum):
    PROVIDER = "provider"
    CAPABILITY = "capability"
    COST = "cost"
    UNSUPPORTED = "unsupported"
    CONFIRMATION = "confirmation"


class PlanWarning(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str
    message: str
    kind: WarningKind
    step_id: str | None = None


class ProviderRequirement(BaseModel):
    model_config = ConfigDict(extra="allow")
    chain: Chain
    capability: str
    provider: str | None = None
    available: bool | None = None


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    step_id: str
    order: int = Field(ge=1)
    title: str
    description: str = ""
    step_type: StepType
    status: StepStatus = StepStatus.PROPOSED
    target_type: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    chain: Chain | None = None
    assets: list[str] = Field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    provider: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    reason: str
    evidence_basis: list[str] = Field(default_factory=list)
    optional: bool = False
    enabled: bool = True
    estimated_records: int | None = Field(default=None, ge=0)
    estimated_api_calls: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    requires_confirmation: bool = False
    can_cancel: bool = True
    warnings: list[PlanWarning] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    plan_id: str
    case_id: str
    generated_at: datetime
    planner_type: PlannerType = PlannerType.DETERMINISTIC
    goals: list[InvestigationGoal]
    steps: list[PlanStep]
    prerequisites: list[str] = Field(default_factory=list)
    estimated_scope: dict[str, Any] = Field(default_factory=dict)
    provider_requirements: list[ProviderRequirement] = Field(default_factory=list)
    possible_costs: Decimal | None = None
    warnings: list[PlanWarning] = Field(default_factory=list)
    user_confirmation_required: bool = True
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None
    plan_version: int = 1
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)

    @field_validator("generated_at", "confirmed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("plan timestamps must be timezone-aware")
        return value

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None and bool(self.confirmed_by)


class PlanConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    confirmed_by: str
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    enabled_step_ids: list[str] = Field(default_factory=list)

    @field_validator("confirmed_at")
    @classmethod
    def confirmation_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmation timestamp must be timezone-aware")
        return value


def plan_now() -> datetime:
    return datetime.now(timezone.utc)
