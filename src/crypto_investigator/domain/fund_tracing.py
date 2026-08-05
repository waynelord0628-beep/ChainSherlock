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

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("An off-ramp candidate requires evidence references")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
