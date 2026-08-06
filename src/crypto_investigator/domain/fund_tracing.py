"""Public data contracts for future evidence-based fund tracing.

These models define trace inputs and outputs only. They do not infer paths,
query providers, allocate funds, or identify an off-ramp.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class SeedType(StrEnum):
    ADDRESS = "address"
    TRANSACTION_HASH = "transaction_hash"
    VICTIM_TRANSFER = "victim_transfer"
    SELECTED_OUTGOING_TRANSACTION = "selected_outgoing_transaction"


class AllocationMethod(StrEnum):
    DIRECT_TRANSACTION = "direct_transaction"
    FIFO = "fifo"
    PROPORTIONAL = "proportional"
    MANUAL = "manual"


class TraceDirection(StrEnum):
    FORWARD = "forward"
    BACKWARD = "backward"
    BIDIRECTIONAL = "bidirectional"


class TraceRunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class FlowPatternType(StrEnum):
    AGGREGATION = "aggregation"
    DISPERSION = "dispersion"
    RETURN_FLOW = "return_flow"
    CYCLIC_FLOW = "cyclic_flow"
    SHARED_COUNTERPARTY = "shared_counterparty"
    REVENUE_SHARE_CANDIDATE = "revenue_share_candidate"
    OFF_RAMP_CONTACT = "off_ramp_contact"


class StopConditionType(StrEnum):
    CONFIRMED_EXCHANGE_OR_VASP = "confirmed_exchange_or_vasp"
    PAYMENT_SERVICE = "payment_service"
    OTC_CANDIDATE = "otc_candidate"
    MIXER = "mixer"
    BRIDGE = "bridge"
    NO_FURTHER_OUTGOING_ACTIVITY = "no_further_outgoing_activity"
    BELOW_MATERIALITY_THRESHOLD = "below_materiality_threshold"
    MAX_DEPTH_REACHED = "max_depth_reached"
    PROVIDER_INCOMPLETE = "provider_incomplete"
    MANUAL_STOP = "manual_stop"


def _public_value(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_public_value(item) for item in value]
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _public_value(item) for key, item in value.items()}
    return value


class SerializableTraceContract:
    def to_dict(self) -> dict[str, Any]:
        return _public_value(asdict(self))


@dataclass(frozen=True, slots=True)
class TraceSeed(SerializableTraceContract):
    seed_type: SeedType
    value: str
    chain: str
    asset: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Trace seed value is required")


@dataclass(frozen=True, slots=True)
class TraceNode(SerializableTraceContract):
    node_id: str
    chain: str
    address: str
    transaction_hash: str | None
    asset: str
    amount: Decimal
    timestamp: datetime
    hop: int
    role: str
    label_status: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TraceEdge(SerializableTraceContract):
    edge_id: str
    from_address: str
    to_address: str
    transaction_hash: str
    asset: str
    amount: Decimal
    timestamp: datetime
    allocation_method: AllocationMethod
    confidence: Decimal
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.transaction_hash.strip():
            raise ValueError("A trace edge requires a real transaction hash")
        if not self.evidence_refs:
            raise ValueError("A trace edge requires evidence references")


@dataclass(frozen=True, slots=True)
class TraceScope(SerializableTraceContract):
    scope_type: str
    max_depth: int
    max_nodes: int
    max_records: int
    min_material_amount: Decimal
    asset_filters: tuple[str, ...] = ()
    date_from: datetime | None = None
    date_to: datetime | None = None
    direction: TraceDirection = TraceDirection.BIDIRECTIONAL
    timezone: str = "Asia/Taipei"
    max_edges_per_node: int = 20

    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        if self.max_nodes < 1 or self.max_records < 1:
            raise ValueError("trace safety limits must be positive")
        if self.max_edges_per_node < 1:
            raise ValueError("max_edges_per_node must be positive")
        if self.min_material_amount < 0:
            raise ValueError("min_material_amount cannot be negative")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be after date_to")


@dataclass(frozen=True, slots=True)
class FundLot(SerializableTraceContract):
    """An incoming asset lot available for deterministic FIFO allocation."""

    lot_id: str
    source_transaction_hash: str
    source_address: str
    asset: str
    original_amount: Decimal
    remaining_amount: Decimal
    received_at: datetime
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_transaction_hash.strip() or not self.evidence_refs:
            raise ValueError("A fund lot requires a transaction hash and evidence")
        if self.original_amount <= 0:
            raise ValueError("original_amount must be positive")
        if not Decimal("0") <= self.remaining_amount <= self.original_amount:
            raise ValueError("remaining_amount must be within the original lot")


@dataclass(frozen=True, slots=True)
class AllocationSlice(SerializableTraceContract):
    """Analytical allocation; it never replaces the underlying transaction edge."""

    allocation_id: str
    lot_id: str
    outgoing_edge_id: str
    asset: str
    amount: Decimal
    method: AllocationMethod
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("allocated amount must be positive")
        if self.method is AllocationMethod.DIRECT_TRANSACTION:
            raise ValueError("An allocation slice must use an analytical method")
        if not self.evidence_refs:
            raise ValueError("An allocation slice requires evidence")


@dataclass(frozen=True, slots=True)
class TraceFrontierItem(SerializableTraceContract):
    address: str
    chain: str
    asset: str
    hop: int
    direction: TraceDirection
    priority: Decimal
    material_amount: Decimal
    parent_edge_id: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.hop < 0:
            raise ValueError("hop cannot be negative")


@dataclass(frozen=True, slots=True)
class TraceCheckpoint(SerializableTraceContract):
    """Serializable continuation state; provider secrets are intentionally absent."""

    run_id: str
    status: TraceRunStatus
    frontier: tuple[TraceFrontierItem, ...]
    visited_addresses: tuple[str, ...]
    visited_transaction_hashes: tuple[str, ...]
    provider_cursors: dict[str, str]
    completed_edge_ids: tuple[str, ...]
    saved_at: datetime
    checkpoint_version: int = 1


@dataclass(frozen=True, slots=True)
class FlowPatternFinding(SerializableTraceContract):
    finding_id: str
    pattern_type: FlowPatternType
    asset: str
    hop: int
    address_refs: tuple[str, ...]
    metrics: dict[str, str]
    reason_codes: tuple[str, ...]
    confidence: Decimal
    evidence_refs: tuple[str, ...]
    candidate_only: bool = True
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
        if not self.evidence_refs:
            raise ValueError("A flow-pattern finding requires evidence")


@dataclass(frozen=True, slots=True)
class TraceResult(SerializableTraceContract):
    run_id: str
    status: TraceRunStatus
    seed: TraceSeed
    scope: TraceScope
    nodes: tuple[TraceNode, ...]
    edges: tuple[TraceEdge, ...]
    allocations: tuple[AllocationSlice, ...] = ()
    patterns: tuple[FlowPatternFinding, ...] = ()
    off_ramp_candidates: tuple["OffRampCandidate", ...] = ()
    stop_conditions: tuple["StopCondition", ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed_assets = {asset.upper() for asset in self.scope.asset_filters}
        if allowed_assets:
            used_assets = {
                item.asset.upper()
                for item in (*self.nodes, *self.edges, *self.allocations)
            }
            if not used_assets.issubset(allowed_assets):
                raise ValueError("Trace result contains an asset outside its scope")


@dataclass(frozen=True, slots=True)
class StopCondition(SerializableTraceContract):
    condition: StopConditionType
    reason: str
    evidence_refs: tuple[str, ...] = ()
    reached: bool = False


@dataclass(frozen=True, slots=True)
class OffRampCandidate(SerializableTraceContract):
    address: str
    label: str | None
    label_source: str | None
    asset: str
    received_amount: Decimal
    transaction_count: int
    first_receipt: datetime
    last_receipt: datetime
    subsequent_behavior: str
    confidence: Decimal
    evidence_refs: tuple[str, ...]
    recommended_action: str
    limitations: tuple[str, ...] = field(default_factory=tuple)
    category: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("An off-ramp candidate requires evidence references")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
