from pathlib import Path

from crypto_investigator.cases.export import CasePackageExporter
from crypto_investigator.cases.importer import CasePackageImporter
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.results import CaseResult


class CaseExportService:
    def __init__(self, repository: CaseRepository) -> None:
        self.exporter = CasePackageExporter(repository)
        self.importer = CasePackageImporter(repository)

    def export_case(
        self, case_id: str, destination: Path, mode: str, result: CaseResult
    ) -> Path:
        return self.exporter.export(
            case_id, destination, mode=mode, case_result=result
        )

    def validate_package(self, package_path: Path):
        return self.importer.validate(package_path)

    def import_case(self, package_path: Path):
        return self.importer.import_package(package_path)
