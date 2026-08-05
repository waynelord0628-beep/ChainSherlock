"""Budgeted provider collection for multi-hop tracing."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from crypto_investigator.domain.fund_tracing import (
    TraceDirection,
    TraceEdge,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.providers.collector import CollectionResult
from crypto_investigator.providers.trace_adapter import records_to_trace_edges


AddressFetcher = Callable[
    [str, Mapping[str, str], frozenset[str]],
    Awaitable[CollectionResult],
]


@dataclass(frozen=True, slots=True)
class ProviderCursorState:
    address: str
    capability: str
    next_cursor: str | None
    complete: bool


@dataclass(frozen=True, slots=True)
class ProviderCollectionCheckpoint:
    frontier: tuple[tuple[int, str, str, str], ...]
    visited_states: tuple[str, ...]
    cursor_states: tuple[ProviderCursorState, ...]
    completed_edge_ids: tuple[str, ...]
    checkpoint_version: int = 1


@dataclass(frozen=True, slots=True)
class ProviderTraceCollection:
    status: TraceRunStatus
    edges: tuple[TraceEdge, ...]
    fetched_addresses: tuple[str, ...]
    address_query_count: int
    provider_page_count: int
    rejected_record_count: int
    safe_errors: tuple[str, ...]
    limitations: tuple[str, ...]
    checkpoint: ProviderCollectionCheckpoint | None = None


async def collect_multihop_edges(
    *,
    seed: TraceSeed,
    scope: TraceScope,
    fetch_address: AddressFetcher,
    max_address_queries: int,
    cancelled: Callable[[], bool] | None = None,
    checkpoint: ProviderCollectionCheckpoint | None = None,
    previous_edges: tuple[TraceEdge, ...] = (),
) -> ProviderTraceCollection:
    """Collect address neighborhoods in deterministic priority order."""

    if max_address_queries < 1:
        raise ValueError("max_address_queries must be positive")
    directions = (
        (TraceDirection.FORWARD, TraceDirection.BACKWARD)
        if scope.direction is TraceDirection.BIDIRECTIONAL
        else (scope.direction,)
    )
    assets = scope.asset_filters or ((seed.asset,) if seed.asset else ())
    frontier = (
        [
            (hop, address, asset, TraceDirection(direction))
            for hop, address, asset, direction in checkpoint.frontier
        ]
        if checkpoint
        else [
            (0, seed.value, asset, direction)
            for asset in assets
            for direction in directions
        ]
    )
    visited = set(checkpoint.visited_states if checkpoint else ())
    fetched_addresses = []
    edge_map = {edge.edge_id: edge for edge in previous_edges}
    page_count = 0
    rejected = 0
    safe_errors = []
    limitations = []
    status = TraceRunStatus.COMPLETED
    address_cache = {}
    cursor_states = {
        (state.address, state.capability): state
        for state in (checkpoint.cursor_states if checkpoint else ())
    }
    resume_frontier = []

    while frontier:
        frontier.sort(key=lambda item: (item[0], item[1], item[2], item[3].value))
        hop, address, asset, direction = frontier.pop(0)
        state_key = f"{direction.value}:{asset}:{address}:{hop}"
        if state_key in visited or hop >= scope.max_depth:
            continue
        if cancelled and cancelled():
            status = TraceRunStatus.CANCELLED
            limitations.append("Collection was cooperatively cancelled.")
            break
        visited.add(state_key)
        if address not in address_cache:
            if len(fetched_addresses) >= max_address_queries:
                status = TraceRunStatus.PARTIAL
                limitations.append("Configured address-query budget was reached.")
                break
            address_states = {
                capability: state
                for (state_address, capability), state in cursor_states.items()
                if state_address == address
            }
            collected = await fetch_address(
                address,
                {
                    capability: state.next_cursor
                    for capability, state in address_states.items()
                    if not state.complete and state.next_cursor
                },
                frozenset(
                    capability
                    for capability, state in address_states.items()
                    if state.complete
                ),
            )
            address_cache[address] = collected
            fetched_addresses.append(address)
            for result in collected.results:
                page_count += max(1, result.pages_fetched)
                if result.truncated or result.available_more:
                    status = TraceRunStatus.PARTIAL
                    limitations.append(
                        f"{result.provider}/{result.capability.value} pagination incomplete."
                    )
                pagination = result.pagination
                cursor_states[(address, result.capability.value)] = ProviderCursorState(
                    address=address,
                    capability=result.capability.value,
                    next_cursor=pagination.next_cursor if pagination else None,
                    complete=bool(pagination and pagination.pagination_complete),
                )
                if not pagination or not pagination.pagination_complete:
                    resume_frontier.append((hop, address, asset, direction))
            safe_errors.extend(error.safe_message for error in collected.errors)
        else:
            collected = address_cache[address]
        converted = records_to_trace_edges(collected.records)
        rejected += converted.rejected_count
        for edge in converted.edges:
            if edge.asset != asset or edge.amount < scope.min_material_amount:
                continue
            edge_map.setdefault(edge.edge_id, edge)

        relevant = tuple(
            edge
            for edge in converted.edges
            if edge.asset == asset and edge.amount >= scope.min_material_amount
        )
        next_items = []
        for edge in relevant:
            if direction is TraceDirection.FORWARD and edge.from_address == address:
                next_items.append((edge.amount, edge.to_address))
            elif direction is TraceDirection.BACKWARD and edge.to_address == address:
                next_items.append((edge.amount, edge.from_address))
        for _, next_address in sorted(next_items, key=lambda item: (-item[0], item[1])):
            if len({item[1] for item in frontier} | set(fetched_addresses)) >= scope.max_nodes:
                status = TraceRunStatus.PARTIAL
                limitations.append("Configured max_nodes safety limit was reached.")
                break
            frontier.append((hop + 1, next_address, asset, direction))

    needs_checkpoint = (
        status in {TraceRunStatus.PARTIAL, TraceRunStatus.CANCELLED}
        or bool(resume_frontier)
    )
    if resume_frontier:
        status = TraceRunStatus.PARTIAL
    pending = tuple(
        dict.fromkeys(
            (
                *(
                    (hop, address, asset, direction.value)
                    for hop, address, asset, direction in frontier
                ),
                *(
                    (hop, address, asset, direction.value)
                    for hop, address, asset, direction in resume_frontier
                ),
            )
        )
    )
    pending_state_keys = {
        f"{direction}:{asset}:{address}:{hop}"
        for hop, address, asset, direction in pending
    }
    saved_checkpoint = (
        ProviderCollectionCheckpoint(
            frontier=pending,
            visited_states=tuple(sorted(visited - pending_state_keys)),
            cursor_states=tuple(
                state for _, state in sorted(cursor_states.items())
            ),
            completed_edge_ids=tuple(sorted(edge_map)),
        )
        if needs_checkpoint
        else None
    )
    return ProviderTraceCollection(
        status=status,
        edges=tuple(
            sorted(
                edge_map.values(),
                key=lambda edge: (edge.timestamp, edge.transaction_hash, edge.edge_id),
            )
        ),
        fetched_addresses=tuple(dict.fromkeys(fetched_addresses)),
        address_query_count=len(fetched_addresses),
        provider_page_count=page_count,
        rejected_record_count=rejected,
        safe_errors=tuple(safe_errors),
        limitations=tuple(dict.fromkeys(limitations)),
        checkpoint=saved_checkpoint,
    )
