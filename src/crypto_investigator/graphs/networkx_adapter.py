import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

import networkx as nx

from crypto_investigator.graphs.models import GraphResult


def graphml_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return json.dumps(
            {str(key): graphml_value(item) for key, item in value.items()},
            ensure_ascii=False,
            sort_keys=True,
        )
    if isinstance(value, (tuple, list, set)):
        return json.dumps(
            [graphml_value(item) for item in value],
            ensure_ascii=False,
            sort_keys=True,
        )
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class NetworkXAdapter:
    def convert(self, graph: GraphResult) -> nx.MultiDiGraph:
        result = nx.MultiDiGraph()
        for node in graph.nodes:
            result.add_node(
                node.node_id,
                address=node.address,
                chain=node.chain.value,
                label=node.label or "",
                category=node.category,
                is_target=node.is_target,
                incoming_count=node.incoming_count,
                outgoing_count=node.outgoing_count,
                transaction_count=node.transaction_count,
                assets=graphml_value(node.assets),
                first_seen=graphml_value(node.first_seen),
                last_seen=graphml_value(node.last_seen),
                metadata=graphml_value(node.metadata),
            )
        for edge in graph.edges:
            result.add_edge(
                edge.source,
                edge.target,
                key=edge.edge_id,
                edge_id=edge.edge_id,
                transaction_count=edge.transaction_count,
                assets=graphml_value(edge.assets),
                amounts_by_asset=graphml_value(edge.amounts_by_asset),
                first_seen=graphml_value(edge.first_seen),
                last_seen=graphml_value(edge.last_seen),
                direction=edge.direction.value,
                transaction_hashes=graphml_value(edge.transaction_hashes),
                metadata=graphml_value(edge.metadata),
            )
        result.graph.update(
            {
                "generated_at": graph.metadata.generated_at.isoformat(),
                "target_address": graph.metadata.target_address or "",
                "chain": graph.metadata.chain.value if graph.metadata.chain else "",
                "source_transaction_count": graph.metadata.source_transaction_count,
                "truncated": graph.metadata.truncated,
                "truncation_reason": graph.metadata.truncation_reason or "",
            }
        )
        return result
