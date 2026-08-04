from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class SafeGraphView(QWebEngineView):
    """Loads only an existing local flow.html inside the active case workspace."""

    def load_graph(self, graph_path: Path, case_workspace: Path) -> None:
        resolved = graph_path.resolve()
        root = case_workspace.resolve()
        if resolved.name != "flow.html" or not resolved.is_file():
            raise ValueError("Graph artifact must be an existing flow.html")
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("Graph artifact is outside the case workspace") from exc
        self.setUrl(QUrl.fromLocalFile(str(resolved)))
