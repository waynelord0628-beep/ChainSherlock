import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.domain.transaction import Chain, Direction
from crypto_investigator.graphs.errors import GraphSerializationError
from crypto_investigator.graphs.models import (
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphResult,
    GraphWarning,
)


class JsonGraphExporter:
    def write(self, graph: GraphResult, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                AnalysisExporter.to_primitive(graph),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def read(self, path: Path) -> GraphResult:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            warnings = tuple(GraphWarning(**item) for item in value["warnings"])
            metadata_value = value["metadata"]
            filters = dict(metadata_value.get("filters", {}))
            for key in (
                "include_assets",
                "exclude_assets",
                "include_addresses",
                "exclude_addresses",
            ):
                if key in filters:
                    filters[key] = tuple(filters[key])
            for key in ("date_from", "date_to"):
                if filters.get(key):
                    filters[key] = datetime.fromisoformat(filters[key])
            metadata = GraphMetadata(
                generated_at=datetime.fromisoformat(metadata_value["generated_at"]),
                target_address=metadata_value.get("target_address"),
                chain=Chain(metadata_value["chain"]) if metadata_value.get("chain") else None,
                source_transaction_count=metadata_value["source_transaction_count"],
                included_node_count=metadata_value["included_node_count"],
                included_edge_count=metadata_value["included_edge_count"],
                excluded_node_count=metadata_value["excluded_node_count"],
                excluded_edge_count=metadata_value["excluded_edge_count"],
                filters=filters,
                truncated=metadata_value["truncated"],
                truncation_reason=metadata_value.get("truncation_reason"),
                warnings=tuple(
                    GraphWarning(**item) for item in metadata_value.get("warnings", [])
                ),
                source_completeness=metadata_value.get(
                    "source_completeness", "complete"
                ),
                missing_data=tuple(metadata_value.get("missing_data", [])),
                provider_errors=tuple(metadata_value.get("provider_errors", [])),
                rejected_record_count=metadata_value.get(
                    "rejected_record_count", 0
                ),
            )
            nodes = tuple(
                GraphNode(
                    node_id=item["node_id"],
                    address=item["address"],
                    chain=Chain(item["chain"]),
                    label=item.get("label"),
                    category=item.get("category", "unknown"),
                    is_target=item.get("is_target", False),
                    incoming_count=item.get("incoming_count", 0),
                    outgoing_count=item.get("outgoing_count", 0),
                    transaction_count=item.get("transaction_count", 0),
                    assets=tuple(item.get("assets", [])),
                    first_seen=self._time(item.get("first_seen")),
                    last_seen=self._time(item.get("last_seen")),
                    metadata=item.get("metadata", {}),
                )
                for item in value["nodes"]
            )
            edges = tuple(
                GraphEdge(
                    edge_id=item["edge_id"],
                    source=item["source"],
                    target=item["target"],
                    transaction_count=item["transaction_count"],
                    assets=tuple(item["assets"]),
                    amounts_by_asset={
                        asset: Decimal(amount)
                        for asset, amount in item["amounts_by_asset"].items()
                    },
                    first_seen=self._time(item.get("first_seen")),
                    last_seen=self._time(item.get("last_seen")),
                    direction=Direction(item["direction"]),
                    transaction_hashes=tuple(item["transaction_hashes"]),
                    metadata=item.get("metadata", {}),
                )
                for item in value["edges"]
            )
            return GraphResult(nodes, edges, metadata, warnings)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise GraphSerializationError("Unable to deserialize graph JSON") from error

    @staticmethod
    def _time(value):
        return datetime.fromisoformat(value) if value else None
