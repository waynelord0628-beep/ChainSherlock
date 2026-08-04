from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class HumanReviewStatus(str, Enum):
    NOT_REVIEWED = "not_reviewed"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class NarrativeInput:
    report_metadata: Mapping[str, Any]
    target_address: str
    chain: str | None
    analysis_period: Mapping[str, Any]
    completeness: str
    provider_limits: tuple[str, ...]
    asset_summaries: tuple[Mapping[str, Any], ...]
    direction_reconciliation: Mapping[str, Any]
    funding_sources: tuple[Mapping[str, Any], ...]
    outgoing_destinations: tuple[Mapping[str, Any], ...]
    funding_transitions: tuple[Mapping[str, Any], ...]
    operation_stages: tuple[Mapping[str, Any], ...]
    dormancy: tuple[Mapping[str, Any], ...]
    holding_time: tuple[Mapping[str, Any], ...]
    transfer_patterns: tuple[Mapping[str, Any], ...]
    concentration_metrics: Mapping[str, Any]
    counterparty_roles: tuple[Mapping[str, Any], ...]
    label_matches: tuple[Mapping[str, Any], ...]
    observations: tuple[Mapping[str, Any], ...]
    conclusion_facts: tuple[Mapping[str, Any], ...]
    limitations: tuple[str, ...]
    evidence_index: tuple[Mapping[str, Any], ...]
    language: str = "zh-TW"
    tone: str = "professional"
    requested_sections: tuple[str, ...] = ()
    omitted_counts: Mapping[str, int] = field(default_factory=dict)
    schema_version: str = "7.0"


@dataclass(frozen=True, slots=True)
class NarrativeMetadata:
    provider: str
    model: str
    prompt_version: str
    generated_at: datetime
    status: str
    fallback_used: bool
    input_sha256: str
    schema_version: str = "7.0"


@dataclass(frozen=True, slots=True)
class NarrativeCitation:
    citation_id: str
    evidence_id: str
    section: str


@dataclass(frozen=True, slots=True)
class NarrativeParagraph:
    text: str
    citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativeSection:
    section_id: str
    title: str
    paragraphs: tuple[NarrativeParagraph, ...]


@dataclass(frozen=True, slots=True)
class NarrativeClaim:
    claim_id: str
    section: str
    statement: str
    claim_type: str
    fact_codes: tuple[str, ...] = ()
    observation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    numeric_values: tuple[str, ...] = ()
    confidence: str = "medium"
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativeWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class NarrativeValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    checked_claims: int = 0


@dataclass(frozen=True, slots=True)
class NarrativeResult:
    metadata: NarrativeMetadata
    executive_summary: NarrativeSection | None = None
    target_profile: NarrativeSection | None = None
    funding_narrative: NarrativeSection | None = None
    outgoing_narrative: NarrativeSection | None = None
    stage_narrative: NarrativeSection | None = None
    dormancy_narrative: NarrativeSection | None = None
    holding_time_narrative: NarrativeSection | None = None
    pattern_narrative: NarrativeSection | None = None
    counterparty_narrative: NarrativeSection | None = None
    alternative_explanations: NarrativeSection | None = None
    investigative_leads: NarrativeSection | None = None
    limitations: NarrativeSection | None = None
    conclusion: NarrativeSection | None = None
    claims: tuple[NarrativeClaim, ...] = ()
    citations: tuple[NarrativeCitation, ...] = ()
    warnings: tuple[NarrativeWarning, ...] = ()
    validation: NarrativeValidationResult = field(
        default_factory=lambda: NarrativeValidationResult(valid=False)
    )
    review_status: HumanReviewStatus = HumanReviewStatus.NOT_REVIEWED
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
