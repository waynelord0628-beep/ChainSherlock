from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class InvestigationMetadata:
    target_address: str
    chain: str | None
    generated_at: datetime
    source_transaction_count: int
    analysis_completeness: str
    graph_completeness: str
    source_date_from: datetime | None
    source_date_to: datetime | None
    assets: tuple[str, ...]
    settings_snapshot: Mapping[str, Any]
    investigation_version: str = "6.5"


@dataclass(frozen=True, slots=True)
class InvestigationWarning:
    code: str
    message: str
    confidence: str = "medium"


@dataclass(frozen=True, slots=True)
class InvestigationEvidenceRef:
    evidence_id: str
    feature: str
    source_type: str
    source_reference: str
    tx_hashes: tuple[str, ...] = ()
    addresses: tuple[str, ...] = ()
    calculation: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class InvestigationSettings:
    dormant_days: int = 30
    batch_window_minutes: int = 5
    batch_minimum_count: int = 3
    fixed_amount_minimum_count: int = 3
    concentration_threshold: Decimal = Decimal("0.60")
    change_threshold: Decimal = Decimal("0.20")
    timezone: str = "Asia/Taipei"
    funding_window_days: int = 30
    initial_funding_window_days: int = 7
    minimum_funding_transactions: int = 2
    minimum_funding_amount: Decimal = Decimal("0")
    dominant_source_min_share: Decimal = Decimal("0.50")
    transition_persistence_days: int = 7


@dataclass(frozen=True, slots=True)
class FundingSource:
    address: str
    transaction_count: int
    transaction_ratio: Decimal
    amounts_by_asset: Mapping[str, Decimal]
    first_funding: datetime | None
    last_funding: datetime | None
    rank: int
    chain: str | None = None
    label: str | None = None
    category: str | None = None
    assets: tuple[str, ...] = ()
    incoming_count: int = 0
    share_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    active_days: int = 0
    average_amount_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    median_amount_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    maximum_amount_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    evidence_transaction_hashes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FundingPeriod:
    period: str
    main_source: str | None
    source_count: int
    transaction_count: int
    concentration: Decimal


@dataclass(frozen=True, slots=True)
class FundingTransition:
    occurred_at: datetime
    previous_source: str
    current_source: str
    asset: str | None = None
    previous_period_start: datetime | None = None
    previous_period_end: datetime | None = None
    new_period_start: datetime | None = None
    old_source_share: Decimal = Decimal("0")
    new_source_share: Decimal = Decimal("0")
    reason_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @property
    def new_source(self) -> str:
        return self.current_source


@dataclass(frozen=True, slots=True)
class FundingAnalysis:
    sources: tuple[FundingSource, ...]
    periods: tuple[FundingPeriod, ...]
    transitions: tuple[FundingTransition, ...]
    concentration: Decimal
    concentration_by_asset: Mapping[str, Decimal] = field(default_factory=dict)
    top_sources_by_asset: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    first_source_by_asset: Mapping[str, str] = field(default_factory=dict)
    latest_source_by_asset: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InitialFundingCandidate:
    asset: str
    amount: Decimal
    source: str
    occurred_at: datetime
    transaction_hash: str
    dust_like: bool
    label_exists: bool
    confidence: str


@dataclass(frozen=True, slots=True)
class OperationStage:
    stage: str
    started_at: datetime | None
    ended_at: datetime | None
    transaction_count: int
    transaction_frequency: Decimal
    concentration: Decimal


@dataclass(frozen=True, slots=True)
class DormantPeriod:
    started_at: datetime
    ended_at: datetime
    dormant_days: int
    reactivated: bool
    post_recovery_average_amount_by_asset: Mapping[str, Decimal]
    post_recovery_daily_frequency: Decimal
    behavior_changed: bool


@dataclass(frozen=True, slots=True)
class ConcentrationMetrics:
    top10_ratio: Decimal
    top20_ratio: Decimal
    top50_ratio: Decimal
    herfindahl_index: Decimal
    gini: Decimal
    entropy: Decimal
    top1_ratio: Decimal = Decimal("0")
    top3_ratio: Decimal = Decimal("0")
    top5_ratio: Decimal = Decimal("0")
    normalized_herfindahl_index: Decimal = Decimal("0")
    effective_counterparty_count: Decimal = Decimal("0")
    by_asset_direction: Mapping[str, Mapping[str, Decimal]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LabelRecord:
    address: str
    label: str
    category: str
    source: str = "local"
    chain: str = "unknown"
    confidence: str = "medium"
    notes: str = ""
    first_seen: datetime | None = None
    last_verified: datetime | None = None
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceDetection:
    address: str
    service_type: str
    matched_rules: tuple[str, ...]
    label: str | None = None
    category: str | None = None


@dataclass(frozen=True, slots=True)
class DistributionMetrics:
    matched_transfer_count: int
    average_holding_seconds: Decimal | None
    median_holding_seconds: Decimal | None


@dataclass(frozen=True, slots=True)
class TransferPattern:
    fixed_amounts: Mapping[str, tuple[Decimal, ...]]
    integer_amount_ratio: Decimal
    amount_suffix_counts: Mapping[str, int]
    batch_outgoing_count: int
    batch_incoming_count: int


@dataclass(frozen=True, slots=True)
class RelationshipResult:
    common_counterparties: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    common_sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    common_destinations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BehaviorSummary:
    funding_pattern: str
    distribution_pattern: str
    frequency: Decimal
    counterparty_pattern: str
    activity_pattern: str
    operation_stages: tuple[str, ...]
    dormant: bool
    recovery: bool


@dataclass(frozen=True, slots=True)
class Observation:
    code: str
    occurred_at: datetime | None
    facts: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ConclusionFacts:
    funding_source_changed: bool
    dormant_days: int
    main_counterparty_ratio: Decimal
    top_provider_changed: bool
    batch_distribution: bool
    funding_concentration: Decimal
    reactivated: bool


@dataclass(frozen=True, slots=True)
class DirectionReconciliation:
    transaction_count: int
    incoming_count: int
    outgoing_count: int
    self_transfer_count: int
    neutral_count: int
    unclassified_direction_count: int
    failed_transaction_count: int
    duplicate_removed_count: int
    reconciled: bool


@dataclass(frozen=True, slots=True)
class ConclusionFact:
    fact_code: str
    value: Any
    unit: str | None
    confidence: str
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HoldingTimeStatistics:
    asset: str
    matched_incoming_amount: Decimal
    matched_outgoing_amount: Decimal
    unmatched_incoming_amount: Decimal
    unmatched_outgoing_amount: Decimal
    average_holding_seconds: Decimal | None
    median_holding_seconds: Decimal | None
    minimum_holding_seconds: Decimal | None
    maximum_holding_seconds: Decimal | None
    within_5_minutes_ratio: Decimal
    within_1_hour_ratio: Decimal
    within_24_hours_ratio: Decimal
    within_7_days_ratio: Decimal
    pass_through_event_count: int


@dataclass(frozen=True, slots=True)
class PassThroughEvent:
    asset: str
    incoming_tx_hash: str
    outgoing_tx_hashes: tuple[str, ...]
    incoming_time: datetime
    first_outgoing_time: datetime
    elapsed_seconds: Decimal
    incoming_amount: Decimal
    matched_amount: Decimal
    match_method: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DistributionAnalysis:
    policy: str
    supported: bool
    statistics_by_asset: Mapping[str, HoldingTimeStatistics]
    pass_through_events: tuple[PassThroughEvent, ...]


@dataclass(frozen=True, slots=True)
class CounterpartyRoleProfile:
    address: str
    role: str
    confidence: str
    reason_codes: tuple[str, ...]
    supporting_metrics: Mapping[str, Any]
    label_source: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CounterpartyAnalysis:
    roles: tuple[CounterpartyRoleProfile, ...]
    rankings: Mapping[str, tuple[Mapping[str, Any], ...]]


@dataclass(frozen=True, slots=True)
class ActivityPeriod:
    period: str
    transaction_count: int


@dataclass(frozen=True, slots=True)
class ActivityAnalysis:
    daily: tuple[ActivityPeriod, ...]
    weekly: tuple[ActivityPeriod, ...]
    monthly: tuple[ActivityPeriod, ...]
    average_interval_seconds: Decimal | None
    median_interval_seconds: Decimal | None
    longest_interval_seconds: Decimal | None
    excluded_missing_timestamp_count: int
    timezone: str


@dataclass(frozen=True, slots=True)
class OperationStageAnalysis:
    stages: tuple[OperationStage, ...]


@dataclass(frozen=True, slots=True)
class BatchPattern:
    batch_id: str
    direction: str
    asset: str
    start_time: datetime
    end_time: datetime
    transaction_count: int
    total_amount: Decimal
    counterparties: tuple[str, ...]
    time_span_seconds: Decimal
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FixedAmountPattern:
    asset: str
    amount: Decimal
    occurrence_count: int
    first_seen: datetime | None
    last_seen: datetime | None
    counterparties: tuple[str, ...]
    direction: str
    percentage_of_transactions: Decimal
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoundAmountPattern:
    asset: str
    level: str
    occurrence_count: int
    ratio: Decimal


@dataclass(frozen=True, slots=True)
class TransferPatternAnalysis:
    batches: tuple[BatchPattern, ...]
    fixed_amounts: tuple[FixedAmountPattern, ...]
    round_amounts: tuple[RoundAmountPattern, ...]
    summary: TransferPattern


@dataclass(frozen=True, slots=True)
class SharedCounterpartyRelation:
    relation_type: str
    addresses: tuple[str, ...]
    shared_counterparties: tuple[str, ...]
    assets: tuple[str, ...]
    transaction_count: int
    amounts_by_asset: Mapping[str, Decimal]
    first_seen: datetime | None
    last_seen: datetime | None
    confidence: str
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationshipAnalysis:
    relations: tuple[SharedCounterpartyRelation, ...]
    relationship_depth_limited: bool = True


@dataclass(frozen=True, slots=True)
class LabelMatch:
    address: str
    chain: str
    label: str
    category: str
    source: str
    confidence: str
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class InvestigationResult:
    funding: FundingAnalysis
    stages: tuple[OperationStage, ...]
    dormant_periods: tuple[DormantPeriod, ...]
    counterparty_concentration: ConcentrationMetrics
    services: tuple[ServiceDetection, ...]
    distribution: DistributionMetrics
    transfer_patterns: TransferPattern
    relationships: RelationshipResult
    behavior: BehaviorSummary
    observations: tuple[Observation, ...]
    conclusion_facts: ConclusionFacts
    metadata: Mapping[str, Any] = field(default_factory=dict)
    direction_reconciliation: DirectionReconciliation | None = None
    structured_metadata: InvestigationMetadata | None = None
    warnings: tuple[InvestigationWarning, ...] = ()
    evidence_refs: tuple[InvestigationEvidenceRef, ...] = ()
    conclusion_fact_items: tuple[ConclusionFact, ...] = ()
    label_matches: tuple[LabelMatch, ...] = ()
    distribution_analysis: DistributionAnalysis | None = None
    counterparty_analysis: CounterpartyAnalysis | None = None
    activity: ActivityAnalysis | None = None
    stage_analysis: OperationStageAnalysis | None = None
    transfer_pattern_analysis: TransferPatternAnalysis | None = None
    relationship_analysis: RelationshipAnalysis | None = None
    initial_funding: tuple[InitialFundingCandidate, ...] = ()
