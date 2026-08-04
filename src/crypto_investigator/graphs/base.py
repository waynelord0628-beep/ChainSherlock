from typing import Protocol

from crypto_investigator.analyzers.models import AnalysisResult
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.graphs.models import GraphFilterOptions, GraphResult


class GraphEngine(Protocol):
    def build(
        self,
        analysis: AnalysisResult,
        *,
        chain: Chain,
        target_address: str | None = None,
        options: GraphFilterOptions | None = None,
    ) -> GraphResult:
        """Build a graph only from the public V3 AnalysisResult."""
