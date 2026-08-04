from typing import Protocol

from crypto_investigator.investigation.investigation_result import InvestigationResult


class InvestigationEngine(Protocol):
    def analyze(self, analysis, target_address: str, **kwargs) -> InvestigationResult:
        ...
