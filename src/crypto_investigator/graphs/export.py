from pathlib import Path

from crypto_investigator.graphs.graphml_exporter import GraphMLExporter
from crypto_investigator.graphs.html_renderer import HtmlGraphRenderer
from crypto_investigator.graphs.json_exporter import JsonGraphExporter
from crypto_investigator.graphs.models import GraphFilterOptions, GraphResult


class GraphExporter:
    def export_all(
        self,
        graph: GraphResult,
        output_dir: Path,
        options: GraphFilterOptions | None = None,
    ) -> dict[str, Path]:
        return {
            "json": JsonGraphExporter().write(
                graph, output_dir / "flow_graph.json"
            ),
            "graphml": GraphMLExporter().write(
                graph, output_dir / "flow.graphml"
            ),
            "html": HtmlGraphRenderer().write(
                graph, output_dir / "flow.html", options
            ),
        }
