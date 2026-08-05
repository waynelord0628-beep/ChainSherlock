"""Deterministic, asset-isolated FIFO allocation for fund-tracing analysis."""

from collections import defaultdict, deque
from dataclasses import replace
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    AllocationSlice,
    FundLot,
    TraceEdge,
)


def allocate_fifo(
    *,
    target_address: str,
    edges: tuple[TraceEdge, ...],
) -> tuple[tuple[AllocationSlice, ...], tuple[FundLot, ...]]:
    """Pair inbound lots to later outbound edges without claiming coin identity."""

    incoming = sorted(
        (edge for edge in edges if edge.to_address == target_address),
        key=lambda edge: (edge.timestamp, edge.transaction_hash, edge.edge_id),
    )
    outgoing = sorted(
        (edge for edge in edges if edge.from_address == target_address),
        key=lambda edge: (edge.timestamp, edge.transaction_hash, edge.edge_id),
    )
    queues: dict[str, deque[FundLot]] = defaultdict(deque)
    pending = deque(incoming)
    allocations: list[AllocationSlice] = []
    allocation_number = 0

    for outgoing_edge in outgoing:
        while pending and pending[0].timestamp <= outgoing_edge.timestamp:
            edge = pending.popleft()
            queues[edge.asset].append(
                FundLot(
                    lot_id=f"LOT-{edge.edge_id}",
                    source_transaction_hash=edge.transaction_hash,
                    source_address=edge.from_address,
                    asset=edge.asset,
                    original_amount=edge.amount,
                    remaining_amount=edge.amount,
                    received_at=edge.timestamp,
                    evidence_refs=edge.evidence_refs,
                )
            )

        amount_left = outgoing_edge.amount
        asset_queue = queues[outgoing_edge.asset]
        while amount_left > 0 and asset_queue:
            lot = asset_queue[0]
            allocated = min(lot.remaining_amount, amount_left)
            allocation_number += 1
            allocations.append(
                AllocationSlice(
                    allocation_id=f"FIFO-{allocation_number:06d}",
                    lot_id=lot.lot_id,
                    outgoing_edge_id=outgoing_edge.edge_id,
                    asset=outgoing_edge.asset,
                    amount=allocated,
                    method=AllocationMethod.FIFO,
                    evidence_refs=tuple(
                        dict.fromkeys((*lot.evidence_refs, *outgoing_edge.evidence_refs))
                    ),
                )
            )
            amount_left -= allocated
            remaining = lot.remaining_amount - allocated
            asset_queue.popleft()
            if remaining > 0:
                asset_queue.appendleft(replace(lot, remaining_amount=remaining))

    remaining_lots = tuple(
        lot
        for asset in sorted(queues)
        for lot in queues[asset]
        if lot.remaining_amount > Decimal("0")
    )
    return tuple(allocations), remaining_lots
