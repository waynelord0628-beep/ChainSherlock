from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from crypto_investigator.domain.transaction import Direction


@dataclass(frozen=True, slots=True)
class SummaryResult:
    first_seen: datetime | None
    last_seen: datetime | None
    transaction_count: int
    incoming_count: int
    outgoing_count: int
    unique_counterparties: int
    active_days: int
    assets: tuple[str, ...]
    top_asset: str | None
    average_daily_transactions: float
    unconfirmed_count: int = 0
    missing_timestamp_count: int = 0


@dataclass(frozen=True, slots=True)
class AssetStatistics:
    transaction_count: int
    total_amount: Decimal
    average_amount: Decimal
    median_amount: Decimal
    max_amount: Decimal
    min_amount: Decimal


@dataclass(frozen=True, slots=True)
class TransactionAmountRef:
    tx_hash: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class StatisticsResult:
    incoming_amount: Mapping[str, Decimal]
    outgoing_amount: Mapping[str, Decimal]
    asset_breakdown: Mapping[str, AssetStatistics]
    top_asset: str | None
    average_amount: Mapping[str, Decimal]
    median_amount: Mapping[str, Decimal]
    max_transaction: Mapping[str, TransactionAmountRef]
    min_transaction: Mapping[str, TransactionAmountRef]
    transaction_frequency: float


@dataclass(frozen=True, slots=True)
class Counterparty:
    address: str
    incoming_count: int
    outgoing_count: int
    incoming_amount_by_asset: Mapping[str, Decimal]
    outgoing_amount_by_asset: Mapping[str, Decimal]
    first_seen: datetime | None
    last_seen: datetime | None
    interaction_count: int
    direction: Direction


@dataclass(frozen=True, slots=True)
class TimelineBucket:
    transaction_count: int
    amounts_by_asset: Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class TimelineResult:
    daily: Mapping[str, TimelineBucket]
    monthly: Mapping[str, TimelineBucket]
    hourly_distribution: Mapping[int, int]
    weekly_distribution: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class FlowNode:
    address: str


@dataclass(frozen=True, slots=True)
class FlowEdge:
    source: str
    target: str
    direction: Direction
    weight: Decimal
    asset: str
    timestamp: datetime | None
    tx_hash: str


@dataclass(frozen=True, slots=True)
class FlowResult:
    nodes: tuple[FlowNode, ...]
    edges: tuple[FlowEdge, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    summary: SummaryResult
    statistics: StatisticsResult
    counterparties: tuple[Counterparty, ...]
    timeline: TimelineResult
    flow: FlowResult
    metadata: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
