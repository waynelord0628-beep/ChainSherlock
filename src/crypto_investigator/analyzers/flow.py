from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.models import FlowEdge, FlowNode, FlowResult
from crypto_investigator.utils.analysis import transaction_direction


class FlowAnalyzer:
    name = "flow"

    def analyze(self, context: AnalysisContext) -> FlowResult:
        node_addresses: set[str] = set()
        edges: list[FlowEdge] = []
        for transaction in context.transactions:
            if transaction.from_address is None or transaction.to_address is None:
                continue
            node_addresses.update((transaction.from_address, transaction.to_address))
            edges.append(
                FlowEdge(
                    source=transaction.from_address,
                    target=transaction.to_address,
                    direction=transaction_direction(
                        transaction, context.target_address
                    ),
                    weight=transaction.amount or Decimal("0"),
                    asset=transaction.asset_symbol or "UNKNOWN",
                    timestamp=transaction.timestamp,
                    tx_hash=transaction.tx_hash,
                )
            )
        return FlowResult(
            nodes=tuple(FlowNode(address) for address in sorted(node_addresses)),
            edges=tuple(edges),
        )
