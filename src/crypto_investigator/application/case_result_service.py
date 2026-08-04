from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.results import CaseResult
from crypto_investigator.services.case_artifact_aggregator import CaseArtifactAggregator


class CaseResultService:
    def __init__(self, repository: CaseRepository) -> None:
        self.aggregator = CaseArtifactAggregator(repository)

    def build_case_result(self, case_id: str) -> CaseResult:
        return self.aggregator.aggregate(case_id)
