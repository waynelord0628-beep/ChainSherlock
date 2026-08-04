from pathlib import Path

from crypto_investigator.application.case_result_service import CaseResultService
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.services.case_export_service import CaseExportService


class CasePackageService:
    def __init__(self, repository: CaseRepository) -> None:
        self.results = CaseResultService(repository)
        self.packages = CaseExportService(repository)

    def export_case_package(self, case_id: str, destination: Path, mode: str):
        return self.packages.export_case(
            case_id, destination, mode, self.results.build_case_result(case_id)
        )

    def validate_case_package(self, package_path: Path):
        return self.packages.validate_package(package_path)

    def import_case_package(self, package_path: Path):
        return self.packages.import_case(package_path)
