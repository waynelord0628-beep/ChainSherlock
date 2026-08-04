from pathlib import Path

import networkx as nx

from crypto_investigator.graphs.errors import GraphExportError
from crypto_investigator.graphs.models import GraphResult
from crypto_investigator.graphs.networkx_adapter import NetworkXAdapter


class GraphMLExporter:
    def write(self, graph: GraphResult, path: Path) -> Path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            nx.write_graphml(NetworkXAdapter().convert(graph), path)
            return path
        except (OSError, nx.NetworkXError) as error:
            raise GraphExportError("Unable to export GraphML") from error
