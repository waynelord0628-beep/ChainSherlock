from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Mapping

from crypto_investigator.domain.transaction import Chain, Direction


@dataclass(frozen=True, slots=True)
class GraphWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class GraphFilterOptions:
    top_counterparties: int = 30
    minimum_transaction_count: int = 1
    include_assets: tuple[str, ...] = ()
    exclude_assets: tuple[str, ...] = ()
    include_addresses: tuple[str, ...] = ()
    exclude_addresses: tuple[str, ...] = ()
    incoming_only: bool = False
    outgoing_only: bool = False
    date_from: datetime | None = None
    date_to: datetime | None = None
    maximum_nodes: int = 100
    maximum_edges: int = 200
    maximum_transaction_hashes_per_edge: int = 100
    maximum_tooltip_length: int = 1000
    sort_by: str = "transactions"
    sort_asset: str | None = None


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    address: str
    chain: Chain
    label: str | None = None
    category: str = "unknown"
    is_target: bool = False
    incoming_count: int = 0
    outgoing_count: int = 0
    transaction_count: int = 0
    assets: tuple[str, ...] = ()
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    source: str
    target: str
    transaction_count: int
    assets: tuple[str, ...]
    amounts_by_asset: Mapping[str, Decimal]
    first_seen: datetime | None
    last_seen: datetime | None
    direction: Direction
    transaction_hashes: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphMetadata:
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    target_address: str | None = None
    chain: Chain | None = None
    source_transaction_count: int = 0
    included_node_count: int = 0
    included_edge_count: int = 0
    excluded_node_count: int = 0
    excluded_edge_count: int = 0
    filters: Mapping[str, Any] = field(default_factory=dict)
    truncated: bool = False
    truncation_reason: str | None = None
    warnings: tuple[GraphWarning, ...] = ()
    source_completeness: str = "complete"
    missing_data: tuple[str, ...] = ()
    provider_errors: tuple[Mapping[str, Any], ...] = ()
    rejected_record_count: int = 0


@dataclass(frozen=True, slots=True)
class GraphResult:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    metadata: GraphMetadata
    warnings: tuple[GraphWarning, ...] = ()
