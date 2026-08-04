from dataclasses import dataclass
from typing import Any, Protocol

from crypto_investigator.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Domain-only input shared by every analyzer."""

    transactions: tuple[Transaction, ...]
    target_address: str | None = None


class Analyzer(Protocol):
    name: str

    def analyze(self, context: AnalysisContext) -> Any:
        """Analyze only canonical Domain Transactions."""
