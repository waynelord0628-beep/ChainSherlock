"""Deterministic traversal over evidence-backed transaction edges."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import (
    StopCondition,
    StopConditionType,
    TraceCheckpoint,
    TraceDirection,
    TraceFrontierItem,
    TraceNode,
    TraceResult,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
    TraceEdge,
)


CancelCheck = Callable[[], bool]


def trace_multihop(
    *,
    run_id: str,
    seed: TraceSeed,
    scope: TraceScope,
    available_edges: tuple[TraceEdge, ...],
    checkpoint: TraceCheckpoint | None = None,
    previous_result: TraceResult | None = None,
    cancelled: CancelCheck | None = None,
    terminal_addresses: dict[str, StopCondition] | None = None,
) -> tuple[TraceResult, TraceCheckpoint | None]:
    """Traverse forward/backward without inventing edges or merging assets."""

    allowed_assets = {item.upper() for item in scope.asset_filters}
    edges = tuple(
        edge
        for edge in available_edges
        if (not allowed_assets or edge.asset.upper() in allowed_assets)
        and edge.amount >= scope.min_material_amount
    )
    edges = tuple(
        sorted(edges, key=lambda edge: (edge.timestamp, edge.transaction_hash, edge.edge_id))
    )

    frontier = list(checkpoint.frontier) if checkpoint else _initial_frontier(seed, scope)
    visited_addresses = set(checkpoint.visited_addresses if checkpoint else ())
    visited_transactions = set(
        checkpoint.visited_transaction_hashes if checkpoint else ()
    )
    selected_edges = list(previous_result.edges if previous_result else ())
    selected_nodes = list(previous_result.nodes if previous_result else ())
    stops = list(previous_result.stop_conditions if previous_result else ())
    status = TraceRunStatus.COMPLETED

    while frontier:
        item = frontier.pop(0)
        frontier_key = f"{item.direction.value}:{item.asset}:{item.address}:{item.hop}"
        if frontier_key in visited_addresses:
            continue
        visited_addresses.add(frontier_key)
        if item.hop >= scope.max_depth:
            stops.append(
                StopCondition(
                    condition=StopConditionType.MAX_DEPTH_REACHED,
                    reason=f"Configured trace depth {scope.max_depth} reached",
                    evidence_refs=item.evidence_refs,
                    reached=True,
                )
            )
            continue
        if terminal_addresses and item.address in terminal_addresses:
            stops.append(terminal_addresses[item.address])
            continue
        if cancelled and cancelled():
            status = TraceRunStatus.CANCELLED
            visited_addresses.discard(frontier_key)
            frontier.insert(0, item)
            break

        candidates = _matching_edges(item, edges)
        if len(candidates) > scope.max_edges_per_node:
            stops.append(
                StopCondition(
                    condition=StopConditionType.MANUAL_STOP,
                    reason=(
                        f"Per-node edge cap {scope.max_edges_per_node} reached "
                        f"at {item.address}; lower-priority edges were not expanded"
                    ),
                    evidence_refs=item.evidence_refs,
                    reached=True,
                )
            )
            candidates = candidates[: scope.max_edges_per_node]
        for edge in candidates:
            if edge.transaction_hash in visited_transactions:
                continue
            if len(selected_edges) >= scope.max_records:
                status = TraceRunStatus.PARTIAL
                visited_addresses.discard(frontier_key)
                frontier.insert(0, item)
                stops.append(
                    StopCondition(
                        condition=StopConditionType.MANUAL_STOP,
                        reason="Configured max_records safety limit reached",
                        evidence_refs=edge.evidence_refs,
                        reached=True,
                    )
                )
                break

            next_address = (
                edge.to_address
                if item.direction is TraceDirection.FORWARD
                else edge.from_address
            )
            if len({node.address for node in selected_nodes} | {next_address}) > scope.max_nodes:
                status = TraceRunStatus.PARTIAL
                visited_addresses.discard(frontier_key)
                frontier.insert(0, item)
                stops.append(
                    StopCondition(
                        condition=StopConditionType.MANUAL_STOP,
                        reason="Configured max_nodes safety limit reached",
                        evidence_refs=edge.evidence_refs,
                        reached=True,
                    )
                )
                break

            visited_transactions.add(edge.transaction_hash)
            selected_edges.append(edge)
            selected_nodes.append(
                TraceNode(
                    node_id=f"NODE-{len(selected_nodes) + 1:06d}",
                    chain=seed.chain,
                    address=next_address,
                    transaction_hash=edge.transaction_hash,
                    asset=edge.asset,
                    amount=edge.amount,
                    timestamp=edge.timestamp,
                    hop=item.hop + 1,
                    role=f"{item.direction.value}_counterparty",
                    label_status="unlabeled",
                    evidence_refs=edge.evidence_refs,
                )
            )
            frontier.append(
                TraceFrontierItem(
                    address=next_address,
                    chain=seed.chain,
                    asset=edge.asset,
                    hop=item.hop + 1,
                    direction=item.direction,
                    priority=edge.amount,
                    material_amount=edge.amount,
                    parent_edge_id=edge.edge_id,
                    evidence_refs=edge.evidence_refs,
                )
            )
        if status in {TraceRunStatus.PARTIAL, TraceRunStatus.CANCELLED}:
            break
        frontier.sort(key=lambda value: (-value.priority, value.address, value.asset))

    result = TraceResult(
        run_id=run_id,
        status=status,
        seed=seed,
        scope=scope,
        nodes=tuple(selected_nodes),
        edges=tuple(selected_edges),
        stop_conditions=tuple(stops),
    )
    if status not in {TraceRunStatus.PARTIAL, TraceRunStatus.CANCELLED}:
        return result, None
    return result, TraceCheckpoint(
        run_id=run_id,
        status=status,
        frontier=tuple(frontier),
        visited_addresses=tuple(sorted(visited_addresses)),
        visited_transaction_hashes=tuple(sorted(visited_transactions)),
        provider_cursors=checkpoint.provider_cursors if checkpoint else {},
        completed_edge_ids=tuple(edge.edge_id for edge in selected_edges),
        saved_at=datetime.now(UTC),
    )


def _initial_frontier(seed: TraceSeed, scope: TraceScope) -> list[TraceFrontierItem]:
    assets = scope.asset_filters or ((seed.asset,) if seed.asset else ())
    directions = (
        (TraceDirection.FORWARD, TraceDirection.BACKWARD)
        if scope.direction is TraceDirection.BIDIRECTIONAL
        else (scope.direction,)
    )
    return [
        TraceFrontierItem(
            address=seed.value,
            chain=seed.chain,
            asset=asset,
            hop=0,
            direction=direction,
            priority=Decimal("Infinity"),
            material_amount=Decimal("0"),
            evidence_refs=seed.evidence_refs,
        )
        for asset in assets
        for direction in directions
    ]


def _matching_edges(
    item: TraceFrontierItem, edges: tuple[TraceEdge, ...]
) -> tuple[TraceEdge, ...]:
    if item.direction is TraceDirection.FORWARD:
        matched = (
            edge
            for edge in edges
            if edge.from_address == item.address and edge.asset == item.asset
        )
    else:
        matched = (
            edge
            for edge in edges
            if edge.to_address == item.address and edge.asset == item.asset
        )
    return tuple(sorted(matched, key=lambda edge: (-edge.amount, edge.timestamp)))
