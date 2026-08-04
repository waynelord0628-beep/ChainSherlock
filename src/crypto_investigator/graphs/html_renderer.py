import html
from pathlib import Path

from pyvis.network import Network

from crypto_investigator.graphs.errors import GraphRenderError
from crypto_investigator.graphs.models import GraphFilterOptions, GraphResult
from crypto_investigator.graphs.styling import node_color


class HtmlGraphRenderer:
    def write(
        self,
        graph: GraphResult,
        path: Path,
        options: GraphFilterOptions | None = None,
    ) -> Path:
        options = options or GraphFilterOptions()
        try:
            network = Network(
                height="800px",
                width="100%",
                directed=True,
                cdn_resources="in_line",
            )
            for node in graph.nodes:
                title = self._limit(
                    f"Address: {node.address}\nCategory: {node.category}\n"
                    f"Transactions: {node.transaction_count}\n"
                    f"Assets: {', '.join(node.assets)}",
                    options.maximum_tooltip_length,
                )
                network.add_node(
                    node.node_id,
                    label=html.escape(node.label or node.address),
                    title=html.escape(title),
                    color=node_color(node.category, node.is_target),
                    shape="star" if node.is_target else "dot",
                    size=30 if node.is_target else 15,
                )
            for edge in graph.edges:
                amounts = ", ".join(
                    f"{asset}: {amount}"
                    for asset, amount in sorted(edge.amounts_by_asset.items())
                )
                title = self._limit(
                    f"Transactions: {edge.transaction_count}\nAmounts: {amounts}",
                    options.maximum_tooltip_length,
                )
                network.add_edge(
                    edge.source,
                    edge.target,
                    title=html.escape(title),
                    label=html.escape(",".join(edge.assets)),
                    arrows="to",
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            content = network.generate_html(notebook=False)
            if graph.metadata.truncated:
                banner = (
                    '<div role="alert" style="padding:8px;background:#fef3c7">'
                    "Graph data was truncated by configured safety limits."
                    "</div>"
                )
                content = content.replace("<body>", f"<body>{banner}", 1)
            path.write_text(content, encoding="utf-8")
            return path
        except (OSError, ValueError, TypeError) as error:
            raise GraphRenderError("Unable to render graph HTML") from error

    @staticmethod
    def _limit(value: str, maximum: int) -> str:
        return value if len(value) <= maximum else value[: max(0, maximum - 1)] + "…"
