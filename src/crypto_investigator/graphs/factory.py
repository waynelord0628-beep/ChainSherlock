from collections.abc import Callable

from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.errors import GraphBuildError


class GraphFactory:
    _registry: dict[str, Callable[[], GraphBuilder]] = {
        "address_flow": GraphBuilder,
        "transaction_flow": GraphBuilder,
    }

    @classmethod
    def create(cls, graph_type: str) -> GraphBuilder:
        try:
            return cls._registry[graph_type]()
        except KeyError as error:
            raise GraphBuildError(f"Unknown graph type: {graph_type}") from error
