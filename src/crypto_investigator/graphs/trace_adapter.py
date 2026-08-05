"""Create the existing graph artifact model from a multi-hop trace result."""

from collections import defaultdict
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import TraceResult, TraceRunStatus
from crypto_investigator.domain.transaction import Chain, Direction
from crypto_investigator.graphs.builder import node_identity, normalize_node_address
from crypto_investigator.graphs.models import (
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphResult,
    GraphWarning,
)


def trace_result_to_graph(result: TraceResult) -> GraphResult:
    chain = Chain(result.seed.chain)
    target = normalize_node_address(chain, result.seed.value)
    grouped = defaultdict(list)
    for edge in result.edges:
        source = node_identity(chain, edge.from_address)
        destination = node_identity(chain, edge.to_address)
        grouped[(source, destination, edge.asset)].append(edge)

    graph_edges = tuple(
        GraphEdge(
            edge_id=f"{source}|{destination}|{asset}",
            source=source,
            target=destination,
            transaction_count=len(edges),
            assets=(asset,),
            amounts_by_asset={
                asset: sum((edge.amount for edge in edges), Decimal("0"))
            },
            first_seen=min(edge.timestamp for edge in edges),
            last_seen=max(edge.timestamp for edge in edges),
            direction=Direction.UNKNOWN,
            transaction_hashes=tuple(
                sorted({edge.transaction_hash for edge in edges})
            ),
            metadata={
                "evidence_refs": sorted(
                    {ref for edge in edges for ref in edge.evidence_refs}
                ),
                "trace_run_id": result.run_id,
            },
        )
        for (source, destination, asset), edges in sorted(grouped.items())
    )
    off_ramps = {item.address: item for item in result.off_ramp_candidates}
    hop_by_address = defaultdict(list)
    for node in result.nodes:
        hop_by_address[node.address].append(node.hop)
    addresses = {
        address
        for edge in result.edges
        for address in (edge.from_address, edge.to_address)
    } | {result.seed.value}
    nodes = tuple(
        _node(
            chain,
            address,
            target,
            graph_edges,
            off_ramps.get(address),
            hop_by_address.get(address, ()),
        )
        for address in sorted(addresses)
    )
    truncated = result.status in {
        TraceRunStatus.PARTIAL,
        TraceRunStatus.CANCELLED,
        TraceRunStatus.FAILED,
    }
    warnings = (
        (GraphWarning("trace_incomplete", "Source trace is not complete"),)
        if truncated
        else ()
    )
    return GraphResult(
        nodes,
        graph_edges,
        GraphMetadata(
            target_address=target,
            chain=chain,
            source_transaction_count=len(result.edges),
            included_node_count=len(nodes),
            included_edge_count=len(graph_edges),
            truncated=truncated,
            truncation_reason=result.status.value if truncated else None,
            warnings=warnings,
            source_completeness="partial" if truncated else "complete",
            missing_data=result.limitations,
        ),
        warnings,
    )


def _node(chain, address, target, edges, off_ramp, hops):
    node_id = node_identity(chain, address)
    incoming = [edge for edge in edges if edge.target == node_id]
    outgoing = [edge for edge in edges if edge.source == node_id]
    timestamps = [
        value
        for edge in (*incoming, *outgoing)
        for value in (edge.first_seen, edge.last_seen)
        if value is not None
    ]
    return GraphNode(
        node_id=node_id,
        address=normalize_node_address(chain, address),
        chain=chain,
        label=off_ramp.label if off_ramp else None,
        category=off_ramp.category if off_ramp and off_ramp.category else "unknown",
        is_target=normalize_node_address(chain, address) == target,
        incoming_count=sum(edge.transaction_count for edge in incoming),
        outgoing_count=sum(edge.transaction_count for edge in outgoing),
        transaction_count=sum(
            edge.transaction_count for edge in (*incoming, *outgoing)
        ),
        assets=tuple(
            sorted({asset for edge in (*incoming, *outgoing) for asset in edge.assets})
        ),
        first_seen=min(timestamps) if timestamps else None,
        last_seen=max(timestamps) if timestamps else None,
        metadata={
            "minimum_hop": min(hops) if hops else 0,
            "off_ramp_candidate": bool(off_ramp),
            "off_ramp_confidence": str(off_ramp.confidence) if off_ramp else None,
        },
    )
