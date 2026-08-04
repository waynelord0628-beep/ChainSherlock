from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from crypto_investigator.core.export import ExportPaths, TransactionExporter
from crypto_investigator.domain.transaction import Transaction
from crypto_investigator.importers.base import ImportBatch
from crypto_investigator.importers.factory import ImporterFactory
from crypto_investigator.importers.validator import (
    DataValidator,
    ValidationIssue,
)
from crypto_investigator.normalizers.factory import NormalizerFactory


class PipelineValidationError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__(f"Pipeline validation failed with {len(issues)} issue(s)")


@dataclass(frozen=True, slots=True)
class PipelineResult:
    transactions: tuple[Transaction, ...]
    exports: ExportPaths


class DataPipeline:
    """Reusable Import -> Validate -> Normalize -> Domain -> Export pipeline."""

    def __init__(
        self,
        validator: DataValidator | None = None,
        exporter: TransactionExporter | None = None,
    ) -> None:
        self.validator = validator or DataValidator()
        self.exporter = exporter or TransactionExporter()

    def run(
        self,
        path: Path,
        column_overrides: Mapping[str, str] | None = None,
        output_dir: Path | None = None,
    ) -> PipelineResult:
        importer = ImporterFactory.create(path)
        batch = importer.load(path, column_overrides)
        transactions = self.to_domain(batch)
        destination = output_dir or Path("output") / path.stem
        exports = self.exporter.export(transactions, destination, path)
        return PipelineResult(transactions, exports)

    def to_domain(self, batch: ImportBatch) -> tuple[Transaction, ...]:
        validation = self.validator.validate(batch.records)
        if not validation.is_valid:
            raise PipelineValidationError(validation.issues)

        transactions: list[Transaction] = []
        for record in validation.valid_records:
            chain = NormalizerFactory.chain_for_record(record)
            normalizer = NormalizerFactory.create(chain)
            transactions.append(normalizer.normalize(record))
        return tuple(transactions)
