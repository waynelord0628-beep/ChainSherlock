"""Transaction-level FIFO provenance propagation for bounded fund tracing."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import TraceEdge


@dataclass(frozen=True, slots=True)
class ProvenanceSlice:
    seed_edge_id: str
    incoming_edge_id: str
    outgoing_edge_id: str
    address: str
    next_address: str
    asset: str
    amount: Decimal
    hop: int
    received_at: datetime
    sent_at: datetime
    path_edge_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProvenanceStop:
    seed_edge_id: str
    address: str
    asset: str
    amount: Decimal
    hop: int
    reason: str
    path_edge_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProvenanceResult:
    slices: tuple[ProvenanceSlice, ...]
    stops: tuple[ProvenanceStop, ...]
    rejected_edge_ids: tuple[str, ...]

    @property
    def traced_amount(self) -> Decimal:
        first_hop = {
            (item.seed_edge_id, item.outgoing_edge_id): item.amount
            for item in self.slices
            if item.hop == 1
        }
        return sum(first_hop.values(), Decimal("0"))


@dataclass(frozen=True, slots=True)
class _TrackedLot:
    seed_edge_id: str
    incoming_edge_id: str
    address: str
    asset: str
    amount: Decimal
    received_at: datetime
    hop: int
    path_addresses: tuple[str, ...]
    path_edge_ids: tuple[str, ...]


@dataclass(slots=True)
class _QueueLot:
    edge_id: str
    amount: Decimal
    received_at: datetime
    tracked_parts: deque[tuple[_TrackedLot, Decimal]]


def trace_fifo_provenance(
    *,
    seed_address: str,
    edges: tuple[TraceEdge, ...],
    max_depth: int,
    min_material_amount: Decimal = Decimal("0"),
    complete_addresses: frozenset[str] | None = None,
    terminal_addresses: frozenset[str] = frozenset(),
    max_normalized_amount: Decimal = Decimal("1000000000000000"),
) -> ProvenanceResult:
    """Propagate seed outflows through complete address histories using FIFO.

    Each frontier lot is independently positioned in the complete inbound queue
    of its receiving address. The resulting slices are analytical allocations,
    not proof that identical token units moved through every hop.
    """

    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    if min_material_amount < 0 or max_normalized_amount <= 0:
        raise ValueError("amount limits must be valid")

    valid = []
    rejected = []
    for edge in edges:
        if (
            not edge.amount.is_finite()
            or edge.amount <= 0
            or edge.amount > max_normalized_amount
            or edge.timestamp.tzinfo is None
        ):
            rejected.append(edge.edge_id)
            continue
        valid.append(edge)
    ordered = tuple(
        sorted(valid, key=lambda item: (item.timestamp, item.transaction_hash, item.edge_id))
    )
    incoming_by_address: dict[tuple[str, str], list[TraceEdge]] = defaultdict(list)
    outgoing_by_address: dict[tuple[str, str], list[TraceEdge]] = defaultdict(list)
    for edge in ordered:
        incoming_by_address[(edge.to_address, edge.asset)].append(edge)
        outgoing_by_address[(edge.from_address, edge.asset)].append(edge)

    seed_edges = tuple(
        edge
        for edge in ordered
        if edge.from_address == seed_address
        and edge.amount >= min_material_amount
    )
    frontier = deque(
        _TrackedLot(
            seed_edge_id=edge.edge_id,
            incoming_edge_id=edge.edge_id,
            address=edge.to_address,
            asset=edge.asset,
            amount=edge.amount,
            received_at=edge.timestamp,
            hop=1,
            path_addresses=(seed_address, edge.to_address),
            path_edge_ids=(edge.edge_id,),
        )
        for edge in seed_edges
    )
    slices = []
    stops = []
    visited = set()
    edge_by_id = {edge.edge_id: edge for edge in ordered}

    while frontier:
        current_hop = frontier[0].hop
        level = []
        while frontier and frontier[0].hop == current_hop:
            level.append(frontier.popleft())
        active_by_address: dict[tuple[str, str], list[_TrackedLot]] = defaultdict(list)
        for lot in level:
            state = (
                lot.seed_edge_id,
                lot.incoming_edge_id,
                lot.address,
                lot.hop,
                lot.path_edge_ids,
            )
            if state in visited:
                continue
            visited.add(state)
            if lot.hop >= max_depth:
                stops.append(_stop(lot, "max_depth_reached"))
            elif lot.address in terminal_addresses:
                stops.append(_stop(lot, "confirmed_terminal"))
            elif complete_addresses is not None and lot.address not in complete_addresses:
                stops.append(_stop(lot, "provider_incomplete"))
            else:
                active_by_address[(lot.address, lot.asset)].append(lot)

        for key, lots in active_by_address.items():
            matched = _allocate_tracked_lots(
                tracked=tuple(lots),
                incoming=tuple(incoming_by_address[key]),
                outgoing=tuple(outgoing_by_address[key]),
            )
            matched_lots = {id(lot) for lot, _, _ in matched}
            for lot in lots:
                if id(lot) not in matched_lots:
                    stops.append(_stop(lot, "no_fifo_attributable_outgoing"))
            for lot, edge, amount in matched:
                if amount < min_material_amount:
                    stops.append(
                        _stop(lot, "below_materiality_threshold", amount=amount)
                    )
                    continue
                evidence = tuple(
                    dict.fromkeys(
                        (
                            *edge_by_id[lot.incoming_edge_id].evidence_refs,
                            *edge.evidence_refs,
                        )
                    )
                )
                path_edge_ids = (*lot.path_edge_ids, edge.edge_id)
                slices.append(
                    ProvenanceSlice(
                        seed_edge_id=lot.seed_edge_id,
                        incoming_edge_id=lot.incoming_edge_id,
                        outgoing_edge_id=edge.edge_id,
                        address=lot.address,
                        next_address=edge.to_address,
                        asset=lot.asset,
                        amount=amount,
                        hop=lot.hop,
                        received_at=lot.received_at,
                        sent_at=edge.timestamp,
                        path_edge_ids=path_edge_ids,
                        evidence_refs=evidence,
                    )
                )
                if edge.to_address in lot.path_addresses:
                    stops.append(
                        _stop(
                            lot,
                            "return_or_cycle_detected",
                            amount=amount,
                            path_edge_ids=path_edge_ids,
                        )
                    )
                    continue
                frontier.append(
                    _TrackedLot(
                        seed_edge_id=lot.seed_edge_id,
                        incoming_edge_id=edge.edge_id,
                        address=edge.to_address,
                        asset=lot.asset,
                        amount=amount,
                        received_at=edge.timestamp,
                        hop=lot.hop + 1,
                        path_addresses=(*lot.path_addresses, edge.to_address),
                        path_edge_ids=path_edge_ids,
                    )
                )

    return ProvenanceResult(
        slices=tuple(slices),
        stops=tuple(stops),
        rejected_edge_ids=tuple(sorted(rejected)),
    )


def _allocate_tracked_lots(
    *,
    tracked: tuple[_TrackedLot, ...],
    incoming: tuple[TraceEdge, ...],
    outgoing: tuple[TraceEdge, ...],
) -> tuple[tuple[_TrackedLot, TraceEdge, Decimal], ...]:
    queue: deque[_QueueLot] = deque()
    pending = deque(
        sorted(incoming, key=lambda item: (item.timestamp, item.transaction_hash, item.edge_id))
    )
    tracked_by_edge: dict[str, list[_TrackedLot]] = defaultdict(list)
    for lot in tracked:
        tracked_by_edge[lot.incoming_edge_id].append(lot)
    matched = []
    for outgoing_edge in sorted(
        outgoing, key=lambda item: (item.timestamp, item.transaction_hash, item.edge_id)
    ):
        while pending and pending[0].timestamp <= outgoing_edge.timestamp:
            edge = pending.popleft()
            capacity = edge.amount
            parts: deque[tuple[_TrackedLot, Decimal]] = deque()
            for lot in sorted(
                tracked_by_edge.get(edge.edge_id, ()),
                key=lambda item: (item.seed_edge_id, item.path_edge_ids),
            ):
                part = min(lot.amount, capacity)
                if part <= 0:
                    break
                parts.append((lot, part))
                capacity -= part
            queue.append(
                _QueueLot(
                    edge_id=edge.edge_id,
                    amount=edge.amount,
                    received_at=edge.timestamp,
                    tracked_parts=parts,
                )
            )
        amount_left = outgoing_edge.amount
        while amount_left > 0 and queue:
            current = queue[0]
            consumed = min(current.amount, amount_left)
            tracked_capacity = consumed
            while tracked_capacity > 0 and current.tracked_parts:
                lot, remaining = current.tracked_parts[0]
                tracked_consumed = min(remaining, tracked_capacity)
                matched.append((lot, outgoing_edge, tracked_consumed))
                remaining -= tracked_consumed
                tracked_capacity -= tracked_consumed
                if remaining == 0:
                    current.tracked_parts.popleft()
                else:
                    current.tracked_parts[0] = (lot, remaining)
            current.amount -= consumed
            amount_left -= consumed
            if current.amount == 0:
                queue.popleft()
    return tuple(matched)


def _stop(
    lot: _TrackedLot,
    reason: str,
    *,
    amount: Decimal | None = None,
    path_edge_ids: tuple[str, ...] | None = None,
) -> ProvenanceStop:
    return ProvenanceStop(
        seed_edge_id=lot.seed_edge_id,
        address=lot.address,
        asset=lot.asset,
        amount=lot.amount if amount is None else amount,
        hop=lot.hop,
        reason=reason,
        path_edge_ids=lot.path_edge_ids if path_edge_ids is None else path_edge_ids,
    )
