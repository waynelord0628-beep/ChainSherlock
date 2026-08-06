"""Composition of deterministic multi-hop tracing features."""

from collections.abc import Callable
from dataclasses import replace

from crypto_investigator.domain.fifo_tracing import allocate_fifo
from crypto_investigator.domain.flow_patterns import (
    FlowPatternSettings,
    detect_flow_patterns,
)
from crypto_investigator.domain.fund_tracing import (
    AllocationSlice,
    StopCondition,
    StopConditionType,
    TraceCheckpoint,
    TraceEdge,
    TraceResult,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.domain.multihop_tracing import trace_multihop
from crypto_investigator.domain.off_ramp import (
    LabelLookup,
    detect_behavioral_endpoints,
    detect_off_ramps,
)


class EmptyLabelLookup:
    def check(self, chain: str, address: str) -> tuple:
        return ()


def investigate_fund_trace(
    *,
    run_id: str,
    seed: TraceSeed,
    scope: TraceScope,
    available_edges: tuple[TraceEdge, ...],
    labels: LabelLookup | None = None,
    checkpoint: TraceCheckpoint | None = None,
    previous_result: TraceResult | None = None,
    cancelled: Callable[[], bool] | None = None,
    pattern_settings: FlowPatternSettings = FlowPatternSettings(),
    manual_stop_addresses: tuple[str, ...] = (),
) -> tuple[TraceResult, TraceCheckpoint | None]:
    """Run the reproducible trace pipeline over already acquired edges."""

    label_lookup = labels or EmptyLabelLookup()
    _, available_stops = detect_off_ramps(
        chain=seed.chain,
        edges=available_edges,
        labels=label_lookup,
    )
    stop_by_address = _stop_addresses(available_stops)
    for address in sorted(set(manual_stop_addresses)):
        stop_by_address[address] = StopCondition(
            condition=StopConditionType.MANUAL_STOP,
            reason=f"Analyst-defined manual stop at {address}",
            evidence_refs=seed.evidence_refs,
            reached=True,
        )
    traced, next_checkpoint = trace_multihop(
        run_id=run_id,
        seed=seed,
        scope=scope,
        available_edges=available_edges,
        checkpoint=checkpoint,
        previous_result=previous_result,
        cancelled=cancelled,
        terminal_addresses=stop_by_address,
    )

    addresses = {seed.value}
    addresses.update(node.address for node in traced.nodes)
    allocations = []
    for address in sorted(addresses):
        slices, _ = allocate_fifo(target_address=address, edges=traced.edges)
        allocations.extend(slices)
    allocations = [
        replace(item, allocation_id=f"FIFO-{index:06d}")
        for index, item in enumerate(allocations, start=1)
    ]

    patterns = detect_flow_patterns(
        seed_address=seed.value,
        nodes=traced.nodes,
        edges=traced.edges,
        settings=pattern_settings,
    )
    off_ramps, label_stops = detect_off_ramps(
        chain=seed.chain,
        edges=traced.edges,
        labels=label_lookup,
    )
    behavioral_endpoints = detect_behavioral_endpoints(
        edges=traced.edges,
        excluded_addresses=frozenset(
            {seed.value, *(item.address for item in off_ramps)}
        ),
    )
    result = replace(
        traced,
        allocations=tuple(allocations),
        patterns=patterns,
        off_ramp_candidates=(*off_ramps, *behavioral_endpoints),
        stop_conditions=_unique_stops(
            (
                *traced.stop_conditions,
                *label_stops,
                *(
                    item
                    for address, item in stop_by_address.items()
                    if address in set(manual_stop_addresses)
                ),
            )
        ),
    )
    return result, next_checkpoint


def _stop_addresses(stops: tuple[StopCondition, ...]) -> dict[str, StopCondition]:
    output = {}
    for stop in stops:
        marker = " at "
        if marker in stop.reason:
            output[stop.reason.rsplit(marker, 1)[1]] = stop
    return output


def _unique_stops(stops: tuple[StopCondition, ...]) -> tuple[StopCondition, ...]:
    seen = set()
    output = []
    for stop in stops:
        key = (stop.condition, stop.reason, stop.evidence_refs)
        if key not in seen:
            seen.add(key)
            output.append(stop)
    return tuple(output)
