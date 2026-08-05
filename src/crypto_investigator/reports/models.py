from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping


class AssetInvestigationPriority(StrEnum):
    PRINCIPAL_VALUE_ASSET = "principal_value_asset"
    OPERATIONAL_ASSET = "operational_asset"
    SPAM_OR_LOW_MATERIALITY_ASSET = "spam_or_low_materiality_asset"


@dataclass(frozen=True, slots=True)
class ReportWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ReportLimitation:
    code: str
    description: str


@dataclass(frozen=True, slots=True)
class ReportConclusion:
    completeness: str
    text: str


@dataclass(frozen=True, slots=True)
class ReportTable:
    table_id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    omitted_count: int = 0


@dataclass(frozen=True, slots=True)
class ReportFigure:
    figure_id: str
    title: str
    path: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    evidence_id: str
    evidence_type: str
    source: str
    source_reference: str
    description: str
    collected_at: datetime | None = None
    hash: str | None = None
    chain: str | None = None
    tx_hash: str | None = None
    address: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportCitation:
    citation_id: str
    evidence_id: str
    display_text: str
    source: str
    source_reference: str
    section_id: str


@dataclass(frozen=True, slots=True)
class ReportSection:
    section_id: str
    title: str
    order: int
    content_blocks: tuple[str, ...] = ()
    tables: tuple[ReportTable, ...] = ()
    figures: tuple[ReportFigure, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[ReportWarning, ...] = ()
    limitations: tuple[ReportLimitation, ...] = ()
    section_type: str = "deterministic"
    claims: tuple[str, ...] = ()
    fact_refs: tuple[str, ...] = ()
    observation_refs: tuple[str, ...] = ()
    confidence: str = "deterministic"
    review_status: str = "not_required"


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    report_id: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    report_version: str = "6"
    chain: str | None = None
    target_address: str | None = None
    target_type: str = "address"
    source_type: str = "file"
    source_files: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    analysis_completeness: str = "complete"
    graph_completeness: str = "complete"
    transaction_count: int = 0
    rejected_record_count: int = 0
    warning_count: int = 0
    timezone: str = "UTC"
    language: str = "zh-TW"
    output_directory: str = "."
    scope_type: str = "unavailable"
    requested_date_from: str | None = None
    requested_date_to: str | None = None
    full_history_complete: bool = False
    provider_raw_record_count: int = 0
    normalized_record_count: int = 0
    analysis_record_count: int = 0
    investigation_edge_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    incoming_count: int = 0
    outgoing_count: int = 0
    native_trx_transaction_count: int = 0
    other_asset_transaction_count: int = 0
    micro_excluded_count: int = 0
    retrieval_completeness: str = "unavailable"
    asset_classification_completeness: str = "unavailable"
    material_analysis_scope: str = "unavailable"
    scope_assets: tuple[str, ...] = ()
    principal_assets: tuple[str, ...] = ()
    principal_asset_coverage: str = "unavailable"
    full_address_profile: bool = False
    first_hop_fund_flow_complete: bool = False
    off_ramp_analysis_available: bool = False
    rejected_count: int = 0
    deduplicated_count: int = 0
    failed_count: int = 0
    unclassified_count: int = 0
    excluded_by_scope: int = 0
    report_type: str = "deterministic"
    base_report_version: str = "6"
    ai_enrichment_enabled: bool = False
    ai_provider: str | None = None
    ai_model: str | None = None
    prompt_version: str | None = None
    validation_status: str = "not_requested"
    fallback: bool = False
    fallback_reason: str | None = None
    review_status: str = "not_reviewed"
    deterministic_section_count: int = 0
    ai_section_count: int = 0
    evidence_reference_count: int = 0
    ai_input_tokens: int = 0
    ai_output_token_limit: int = 0
    ai_output_tokens: int = 0
    ai_finish_reason: str | None = None
    benchmark: Mapping[str, Any] = field(default_factory=dict)
    first_hop_product: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportDocument:
    title: str
    metadata: ReportMetadata
    sections: tuple[ReportSection, ...]
    evidence: tuple[ReportEvidence, ...]
    citations: tuple[ReportCitation, ...]
    warnings: tuple[ReportWarning, ...]
    limitations: tuple[ReportLimitation, ...]
    conclusion: ReportConclusion


@dataclass(frozen=True, slots=True)
class ReportExportResult:
    status: str
    files: Mapping[str, str]
    errors: tuple[Mapping[str, Any], ...] = ()
