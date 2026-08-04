from collections import defaultdict
from dataclasses import asdict, replace

from crypto_investigator.analyzers.models import AnalysisResult
from crypto_investigator.domain.transaction import Chain, Direction
from crypto_investigator.graphs.aggregation import EdgeAccumulator
from crypto_investigator.graphs.filtering import GraphFilter
from crypto_investigator.graphs.models import (
    GraphEdge,
    GraphFilterOptions,
    GraphMetadata,
    GraphNode,
    GraphResult,
    GraphWarning,
)


def normalize_node_address(chain: Chain, address: str) -> str:
    value = address.strip()
    return value.lower() if chain is Chain.ETHEREUM else value


def node_identity(chain: Chain, address: str) -> str:
    return f"{chain.value}:{normalize_node_address(chain, address)}"


class GraphBuilder:
    def build(
        self,
        analysis: AnalysisResult,
        *,
        chain: Chain,
        target_address: str | None = None,
        options: GraphFilterOptions | None = None,
    ) -> GraphResult:
        options = options or GraphFilterOptions()
        target = normalize_node_address(chain, target_address) if target_address else None
        accumulators: dict[tuple[str, str, Direction, str], EdgeAccumulator] = {}
        addresses: set[str] = {target} if target else set()

        for edge in analysis.flow.edges:
            source_address = normalize_node_address(chain, edge.source)
            target_address_value = normalize_node_address(chain, edge.target)
            source = node_identity(chain, source_address)
            destination = node_identity(chain, target_address_value)
            asset = edge.asset or "UNKNOWN"
            key = (source, destination, edge.direction, asset)
            accumulator = accumulators.setdefault(
                key, EdgeAccumulator(source, destination, edge.direction, asset)
            )
            accumulator.transaction_count += 1
            accumulator.amount += edge.weight
            if edge.timestamp is not None:
                accumulator.timestamps.append(edge.timestamp)
            accumulator.hashes.add(edge.tx_hash)
            addresses.update((source_address, target_address_value))

        edges = tuple(
            GraphEdge(
                edge_id=f"{source}|{destination}|{direction.value}|{asset}",
                source=source,
                target=destination,
                transaction_count=value.transaction_count,
                assets=(asset,),
                amounts_by_asset={asset: value.amount},
                first_seen=min(value.timestamps) if value.timestamps else None,
                last_seen=max(value.timestamps) if value.timestamps else None,
                direction=direction,
                transaction_hashes=tuple(sorted(value.hashes))[
                    : options.maximum_transaction_hashes_per_edge
                ],
                metadata={
                    "transaction_hashes_truncated": len(value.hashes)
                    > options.maximum_transaction_hashes_per_edge
                },
            )
            for (source, destination, direction, asset), value in sorted(
                accumulators.items(),
                key=lambda item: (
                    item[0][0],
                    item[0][1],
                    item[0][2].value,
                    item[0][3],
                ),
            )
        )
        nodes = self._nodes(chain, addresses, edges, target)
        warnings: list[GraphWarning] = []
        if not edges:
            warnings.append(GraphWarning("no_edges", "Flow contains no graph edges"))
        metadata = GraphMetadata(
            target_address=target,
            chain=chain,
            source_transaction_count=analysis.summary.transaction_count,
            included_node_count=len(nodes),
            included_edge_count=len(edges),
            warnings=tuple(warnings),
            source_completeness=str(analysis.metadata.get("completeness", "complete")),
            missing_data=tuple(analysis.metadata.get("missing_data", ())),
            provider_errors=tuple(analysis.metadata.get("provider_errors", ())),
            rejected_record_count=int(
                analysis.metadata.get("rejected_record_count", 0)
            ),
        )
        return GraphFilter().apply(
            GraphResult(nodes, edges, metadata, tuple(warnings)), options
        )

    @staticmethod
    def _nodes(
        chain: Chain,
        addresses: set[str],
        edges: tuple[GraphEdge, ...],
        target: str | None,
    ) -> tuple[GraphNode, ...]:
        incoming: dict[str, int] = defaultdict(int)
        outgoing: dict[str, int] = defaultdict(int)
        assets: dict[str, set[str]] = defaultdict(set)
        timestamps: dict[str, list] = defaultdict(list)
        for edge in edges:
            outgoing[edge.source] += edge.transaction_count
            incoming[edge.target] += edge.transaction_count
            for node_id in (edge.source, edge.target):
                assets[node_id].update(edge.assets)
                timestamps[node_id].extend(
                    value
                    for value in (edge.first_seen, edge.last_seen)
                    if value is not None
                )
        return tuple(
            GraphNode(
                node_id=node_identity(chain, address),
                address=address,
                chain=chain,
                label=address,
                is_target=address == target,
                incoming_count=incoming[node_identity(chain, address)],
                outgoing_count=outgoing[node_identity(chain, address)],
                transaction_count=(
                    incoming[node_identity(chain, address)]
                    + outgoing[node_identity(chain, address)]
                ),
                assets=tuple(sorted(assets[node_identity(chain, address)])),
                first_seen=(
                    min(timestamps[node_identity(chain, address)])
                    if timestamps[node_identity(chain, address)]
                    else None
                ),
                last_seen=(
                    max(timestamps[node_identity(chain, address)])
                    if timestamps[node_identity(chain, address)]
                    else None
                ),
            )
            for address in sorted(addresses)
        )
