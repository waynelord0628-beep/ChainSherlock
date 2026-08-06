"""Deterministic accounting contracts for evidence-backed fund tracing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable


class AmountStatus(StrEnum):
    KNOWN_AMOUNT = "known_amount"
    UNKNOWN_AMOUNT = "unknown_amount"
    UNAVAILABLE_AMOUNT = "unavailable_amount"
    ZERO_VALUE_EVENT = "zero_value_event"


class PathAllocationType(StrEnum):
    EXCLUSIVE = "exclusive"
    SHARED_CAP = "shared_cap"
    BOTTLENECK_UPPER_BOUND = "bottleneck_upper_bound"
    UNALLOCATED = "unallocated"


class StopClassification(StrEnum):
    VERIFIED_VASP_OR_SERVICE = "verified_vasp_or_service"
    UNVERIFIED_VASP_OR_SERVICE_CANDIDATE = (
        "unverified_vasp_or_service_candidate"
    )
    HIGH_ACTIVITY_AGGREGATION = "high_activity_aggregation"
    HIGH_FAN_OUT = "high_fan_out"
    RAPID_ONWARD_TRANSFER = "rapid_onward_transfer"
    LOW_ACTIVITY_ENDPOINT_CANDIDATE = "low_activity_endpoint_candidate"
    NO_MATERIAL_OUTGOING = "no_material_outgoing"
    MAX_DEPTH_REACHED = "max_depth_reached"
    BELOW_MATERIALITY_THRESHOLD = "below_materiality_threshold"
    PROVIDER_INCOMPLETE = "provider_incomplete"
    AMOUNT_UNAVAILABLE = "amount_unavailable"
    MANUAL_STOP = "manual_stop"


def _public(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class PathAllocation:
    path_id: str
    allocation_type: PathAllocationType
    amount_status: AmountStatus
    exclusive_amount: Decimal | None = None
    shared_cap: Decimal | None = None
    shared_group_id: str | None = None
    bottleneck_upper_bound: Decimal | None = None
    confidence: Decimal = Decimal("0")
    accounting_eligible: bool = False
    evidence_refs: tuple[str, ...] = ()
    limitation: str | None = None

    def __post_init__(self) -> None:
        if not self.path_id.strip():
            raise ValueError("path_id is required")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("confidence must be between 0 and 1")
        for value in (
            self.exclusive_amount,
            self.shared_cap,
            self.bottleneck_upper_bound,
        ):
            if value is not None and value < 0:
                raise ValueError("allocation amounts cannot be negative")
        if self.amount_status in {
            AmountStatus.UNKNOWN_AMOUNT,
            AmountStatus.UNAVAILABLE_AMOUNT,
        } and any(
            value is not None
            for value in (
                self.exclusive_amount,
                self.shared_cap,
                self.bottleneck_upper_bound,
            )
        ):
            raise ValueError("unknown or unavailable amounts cannot carry a value")
        if self.amount_status is AmountStatus.ZERO_VALUE_EVENT:
            values = tuple(
                value
                for value in (
                    self.exclusive_amount,
                    self.shared_cap,
                    self.bottleneck_upper_bound,
                )
                if value is not None
            )
            if any(value != 0 for value in values):
                raise ValueError("zero_value_event can only carry zero")
        if self.allocation_type is PathAllocationType.EXCLUSIVE:
            if self.exclusive_amount is None:
                raise ValueError("exclusive allocation requires exclusive_amount")
            if not self.accounting_eligible:
                raise ValueError("exclusive allocation must be accounting eligible")
        elif self.accounting_eligible:
            raise ValueError("only exclusive allocations may be accounting eligible")
        if self.allocation_type is PathAllocationType.SHARED_CAP:
            if self.shared_cap is None or not self.shared_group_id:
                raise ValueError("shared cap requires amount and shared_group_id")

    def to_dict(self) -> dict[str, Any]:
        return _public(asdict(self))


@dataclass(frozen=True, slots=True)
class BranchConservation:
    branch_id: str
    asset: str
    first_hop_received: Decimal
    allocated_unique: Decimal
    pruned: Decimal
    retained: Decimal
    below_threshold: Decimal
    provider_unresolved: Decimal
    unclassified: Decimal
    shared_cap_total: Decimal
    tolerance: Decimal
    delta: Decimal
    conserved: bool

    @property
    def accounted_total(self) -> Decimal:
        return (
            self.allocated_unique
            + self.pruned
            + self.retained
            + self.below_threshold
            + self.provider_unresolved
            + self.unclassified
        )

    @property
    def resolved_amount(self) -> Decimal:
        return self.allocated_unique + self.pruned + self.retained + self.below_threshold

    @property
    def unresolved_amount(self) -> Decimal:
        return self.provider_unresolved + self.unclassified

    def to_dict(self) -> dict[str, Any]:
        payload = _public(asdict(self))
        payload["accounted_total"] = str(self.accounted_total)
        payload["resolved_amount"] = str(self.resolved_amount)
        payload["unresolved_amount"] = str(self.unresolved_amount)
        return payload


def classify_legacy_path_amount(
    *,
    raw_amount: Decimal | None,
    has_edge_evidence: bool,
    explicit_zero_value_event: bool = False,
) -> AmountStatus:
    """Prevent legacy migration placeholders from appearing as confirmed zero."""

    if raw_amount is None:
        return AmountStatus.UNAVAILABLE_AMOUNT
    if raw_amount != 0:
        return AmountStatus.KNOWN_AMOUNT
    if explicit_zero_value_event and has_edge_evidence:
        return AmountStatus.ZERO_VALUE_EVENT
    if not has_edge_evidence:
        return AmountStatus.UNAVAILABLE_AMOUNT
    return AmountStatus.UNKNOWN_AMOUNT


def reconcile_branch(
    *,
    branch_id: str,
    asset: str,
    first_hop_received: Decimal,
    allocations: Iterable[PathAllocation] = (),
    pruned: Decimal = Decimal("0"),
    retained: Decimal = Decimal("0"),
    below_threshold: Decimal = Decimal("0"),
    provider_unresolved: Decimal = Decimal("0"),
    unclassified: Decimal = Decimal("0"),
    tolerance: Decimal = Decimal("0.000001"),
) -> BranchConservation:
    values = (
        first_hop_received,
        pruned,
        retained,
        below_threshold,
        provider_unresolved,
        unclassified,
        tolerance,
    )
    if any(value < 0 for value in values):
        raise ValueError("conservation inputs cannot be negative")
    items = tuple(allocations)
    allocated_unique = sum(
        (
            item.exclusive_amount or Decimal("0")
            for item in items
            if item.accounting_eligible
        ),
        Decimal("0"),
    )
    shared_groups: dict[str, Decimal] = {}
    for item in items:
        if item.allocation_type is not PathAllocationType.SHARED_CAP:
            continue
        assert item.shared_group_id is not None
        assert item.shared_cap is not None
        previous = shared_groups.get(item.shared_group_id)
        if previous is not None and previous != item.shared_cap:
            raise ValueError("shared group contains conflicting caps")
        shared_groups[item.shared_group_id] = item.shared_cap
    shared_cap_total = sum(shared_groups.values(), Decimal("0"))
    accounted = (
        allocated_unique
        + pruned
        + retained
        + below_threshold
        + provider_unresolved
        + unclassified
    )
    delta = first_hop_received - accounted
    return BranchConservation(
        branch_id=branch_id,
        asset=asset,
        first_hop_received=first_hop_received,
        allocated_unique=allocated_unique,
        pruned=pruned,
        retained=retained,
        below_threshold=below_threshold,
        provider_unresolved=provider_unresolved,
        unclassified=unclassified,
        shared_cap_total=shared_cap_total,
        tolerance=tolerance,
        delta=delta,
        conserved=abs(delta) <= tolerance,
    )


def reconcile_case(
    branches: Iterable[BranchConservation],
    *,
    tolerance: Decimal = Decimal("0.000001"),
) -> BranchConservation:
    items = tuple(branches)
    assets = {item.asset for item in items}
    if len(assets) > 1:
        raise ValueError("case conservation cannot combine different assets")
    return BranchConservation(
        branch_id="CASE-TOTAL",
        asset=next(iter(assets), "UNKNOWN"),
        first_hop_received=sum((item.first_hop_received for item in items), Decimal("0")),
        allocated_unique=sum((item.allocated_unique for item in items), Decimal("0")),
        pruned=sum((item.pruned for item in items), Decimal("0")),
        retained=sum((item.retained for item in items), Decimal("0")),
        below_threshold=sum((item.below_threshold for item in items), Decimal("0")),
        provider_unresolved=sum(
            (item.provider_unresolved for item in items), Decimal("0")
        ),
        unclassified=sum((item.unclassified for item in items), Decimal("0")),
        shared_cap_total=sum((item.shared_cap_total for item in items), Decimal("0")),
        tolerance=tolerance,
        delta=sum((item.delta for item in items), Decimal("0")),
        conserved=all(item.conserved for item in items)
        and abs(sum((item.delta for item in items), Decimal("0"))) <= tolerance,
    )
