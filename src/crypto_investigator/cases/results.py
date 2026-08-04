from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewStatus(StrEnum):
    NOT_REVIEWED = "not_reviewed"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class CaseFact(BaseModel):
    model_config = ConfigDict(extra="allow")
    fact_id: str
    category: str
    statement: str
    structured_value: Any = None
    source_type: str
    source_refs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: str = "high"
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    limitations: list[str] = Field(default_factory=list)


class CaseObservation(BaseModel):
    model_config = ConfigDict(extra="allow")
    observation_id: str
    source_address: str | None = None
    category: str
    factual_statement: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    confidence: str = "medium"
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source_artifact: str


class CandidateType(StrEnum):
    SERVICE = "service_candidate"
    EXCHANGE = "exchange_candidate"
    OTC = "otc_candidate"
    INTERMEDIARY = "intermediary_candidate"
    PAYMENT = "payment_candidate"
    FUNDING = "funding_role_candidate"
    DISTRIBUTION = "distribution_role_candidate"
    OPERATIONAL = "operational_pattern_candidate"
    UNKNOWN = "unknown"


class CaseInterpretation(BaseModel):
    model_config = ConfigDict(extra="allow")
    interpretation_id: str
    title: str
    statement: str
    candidate_type: CandidateType = CandidateType.UNKNOWN
    supporting_facts: list[str] = Field(default_factory=list)
    supporting_observations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: str = "low"
    alternative_explanations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED


class UnresolvedQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")
    question_id: str
    question: str
    related_goals: list[str] = Field(default_factory=list)
    related_addresses: list[str] = Field(default_factory=list)
    related_transactions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_unresolved: str
    required_data: list[str] = Field(default_factory=list)
    priority: str = "normal"
    status: str = "open"
    resolution_notes: str = ""


class RecommendedFollowUp(BaseModel):
    model_config = ConfigDict(extra="allow")
    recommendation_id: str
    title: str
    description: str
    related_goal: str | None = None
    target_addresses: list[str] = Field(default_factory=list)
    target_transactions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str
    expected_answer: str
    external_permission_required: bool = False
    possible_cost: Decimal | None = None
    supported_by_current_system: bool = True
    priority: str = "normal"
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED


class EvidenceIndexEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    evidence_id: str
    evidence_type: str
    description: str
    relative_path: str
    sha256: str | None = None
    size: int | None = None
    source: str
    created_at: datetime | None = None
    related_case_entities: list[str] = Field(default_factory=list)
    related_goals: list[str] = Field(default_factory=list)
    related_facts: list[str] = Field(default_factory=list)
    related_observations: list[str] = Field(default_factory=list)
    integrity_status: str = "unknown"


class AuditSummary(BaseModel):
    entry_count: int = 0
    action_counts: dict[str, int] = Field(default_factory=dict)
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    chain_integrity: bool = False


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int = 1
    case_id: str
    case_number: str | None = None
    title: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    case_status: str
    execution_ids: list[str] = Field(default_factory=list)
    plan_ids: list[str] = Field(default_factory=list)
    investigation_goals: list[dict[str, Any]] = Field(default_factory=list)
    analysis_scope: dict[str, Any] = Field(default_factory=dict)
    chains: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    known_addresses: list[str] = Field(default_factory=list)
    known_transactions: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    execution_summary: dict[str, Any] = Field(default_factory=dict)
    address_results: list[dict[str, Any]] = Field(default_factory=list)
    transaction_results: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_facts: list[CaseFact] = Field(default_factory=list)
    deterministic_observations: list[CaseObservation] = Field(default_factory=list)
    candidate_interpretations: list[CaseInterpretation] = Field(default_factory=list)
    unresolved_questions: list[UnresolvedQuestion] = Field(default_factory=list)
    recommended_follow_ups: list[RecommendedFollowUp] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_index: list[EvidenceIndexEntry] = Field(default_factory=list)
    audit_summary: AuditSummary = Field(default_factory=AuditSummary)
    warnings: list[str] = Field(default_factory=list)
    completeness: str = "complete"
