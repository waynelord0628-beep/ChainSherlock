from dataclasses import asdict, replace
from decimal import Decimal

from crypto_investigator.domain.transaction import Direction
from crypto_investigator.graphs.errors import GraphFilterError
from crypto_investigator.graphs.models import (
    GraphEdge,
    GraphFilterOptions,
    GraphResult,
    GraphWarning,
)


class GraphFilter:
    def apply(
        self, graph: GraphResult, options: GraphFilterOptions
    ) -> GraphResult:
        self._validate(options)
        original_nodes = len(graph.nodes)
        original_edges = len(graph.edges)
        node_by_id = {node.node_id: node for node in graph.nodes}
        include_assets = set(options.include_assets)
        exclude_assets = set(options.exclude_assets)
        include_addresses = set(options.include_addresses)
        exclude_addresses = set(options.exclude_addresses)

        edges = [
            edge
            for edge in graph.edges
            if edge.transaction_count >= options.minimum_transaction_count
            and (not include_assets or bool(include_assets.intersection(edge.assets)))
            and not exclude_assets.intersection(edge.assets)
            and (
                not include_addresses
                or node_by_id[edge.source].address in include_addresses
                or node_by_id[edge.target].address in include_addresses
            )
            and node_by_id[edge.source].address not in exclude_addresses
            and node_by_id[edge.target].address not in exclude_addresses
            and (not options.incoming_only or edge.direction is Direction.INCOMING)
            and (not options.outgoing_only or edge.direction is Direction.OUTGOING)
            and (
                options.date_from is None
                or edge.last_seen is None
                or edge.last_seen >= options.date_from
            )
            and (
                options.date_to is None
                or edge.first_seen is None
                or edge.first_seen <= options.date_to
            )
        ]
        target = next((node for node in graph.nodes if node.is_target), None)
        ranked = self._rank_nodes(graph, edges, options)
        if options.top_counterparties >= 0:
            ranked = ranked[: options.top_counterparties]
        capacity = options.maximum_nodes - (1 if target else 0)
        allowed = {node.node_id for node in ranked[: max(0, capacity)]}
        if target:
            allowed.add(target.node_id)
        edges = [
            edge
            for edge in edges
            if edge.source in allowed and edge.target in allowed
        ]
        edges.sort(key=self._edge_rank)
        edges = edges[: options.maximum_edges]
        referenced = {value for edge in edges for value in (edge.source, edge.target)}
        if target:
            referenced.add(target.node_id)
        nodes = tuple(
            node
            for node in sorted(graph.nodes, key=lambda item: item.node_id)
            if node.node_id in referenced
        )
        truncated = len(nodes) < original_nodes or len(edges) < original_edges
        reasons = []
        if len(nodes) < original_nodes:
            reasons.append("maximum_nodes_or_filters")
        if len(edges) < original_edges:
            reasons.append("maximum_edges_or_filters")
        warnings = list(graph.warnings)
        if truncated:
            warnings.append(
                GraphWarning("graph_truncated", "Graph filters or safety limits excluded data")
            )
        metadata = replace(
            graph.metadata,
            included_node_count=len(nodes),
            included_edge_count=len(edges),
            excluded_node_count=original_nodes - len(nodes),
            excluded_edge_count=original_edges - len(edges),
            filters=asdict(options),
            truncated=truncated,
            truncation_reason=";".join(reasons) if reasons else None,
            warnings=tuple(warnings),
        )
        return GraphResult(nodes, tuple(edges), metadata, tuple(warnings))

    @staticmethod
    def _rank_nodes(graph, edges, options):
        edge_ids = {node_id for edge in edges for node_id in (edge.source, edge.target)}
        nodes = [
            node for node in graph.nodes if not node.is_target and node.node_id in edge_ids
        ]

        def key(node):
            asset_amount = sum(
                (
                    edge.amounts_by_asset.get(options.sort_asset, Decimal("0"))
                    for edge in edges
                    if node.node_id in (edge.source, edge.target)
                ),
                Decimal("0"),
            )
            primary = (
                asset_amount
                if options.sort_by == "asset"
                else node.transaction_count
            )
            return (
                -primary,
                -(node.last_seen.timestamp() if node.last_seen else -1),
                node.node_id,
            )

        return sorted(nodes, key=key)

    @staticmethod
    def _edge_rank(edge: GraphEdge):
        return (
            -edge.transaction_count,
            -(edge.last_seen.timestamp() if edge.last_seen else -1),
            edge.edge_id,
        )

    @staticmethod
    def _validate(options: GraphFilterOptions) -> None:
        if options.incoming_only and options.outgoing_only:
            raise GraphFilterError("incoming_only and outgoing_only are mutually exclusive")
        if options.maximum_nodes < 1 or options.maximum_edges < 0:
            raise GraphFilterError("Graph limits must be non-negative")
        if options.sort_by not in {"transactions", "interactions", "asset"}:
            raise GraphFilterError(f"Unknown sort mode: {options.sort_by}")
        if options.sort_by == "asset" and not options.sort_asset:
            raise GraphFilterError("sort_asset is required for asset sorting")
