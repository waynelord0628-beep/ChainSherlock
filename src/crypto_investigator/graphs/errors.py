class GraphError(Exception):
    pass


class GraphBuildError(GraphError):
    pass


class GraphFilterError(GraphError):
    pass


class GraphExportError(GraphError):
    pass


class GraphRenderError(GraphError):
    pass


class GraphLimitError(GraphError):
    pass


class GraphSerializationError(GraphError):
    pass
