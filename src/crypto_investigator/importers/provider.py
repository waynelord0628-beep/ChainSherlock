from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from crypto_investigator.importers.base import ImportBatch
from crypto_investigator.importers.mapping import ColumnMapping
from crypto_investigator.providers.models import ProviderRawRecord
from crypto_investigator.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class RejectedProviderRecord:
    provider: str
    chain: str
    source_type: str
    tx_hash: str
    raw_reference: str | None
    reasons: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class ProviderPipelineResult:
    transactions: tuple[Transaction, ...]
    rejected_records: tuple[RejectedProviderRecord, ...]


class ProviderRecordImporter:
    def load(self, records: tuple[ProviderRawRecord, ...]) -> ImportBatch:
        canonical = []
        for record in records:
            decimals = record.decimals or 0
            amount = (
                Decimal(record.amount_raw) / (Decimal(10) ** decimals)
                if record.amount_raw is not None
                else Decimal(0)
            )
            canonical.append(
                {
                    "chain": record.chain.value,
                    "tx_hash": record.tx_hash,
                    "timestamp": record.timestamp,
                    "block_number": record.block_number,
                    "from_address": record.from_address,
                    "to_address": record.to_address,
                    "asset_symbol": record.asset_symbol,
                    "asset_contract": record.asset_contract,
                    "amount": amount,
                    "decimals": record.decimals,
                    "transaction_type": record.transaction_type,
                    "success": record.success,
                    "source_provider": record.source_provider,
                    "source_type": record.source_type,
                    "source_metadata": dict(record.metadata),
                    "raw_reference": record.raw_reference,
                }
            )
        return ImportBatch(
            Path("<provider>"),
            tuple(canonical),
            ColumnMapping({key: key for key in canonical[0]}) if canonical else ColumnMapping({}),
        )

    def to_domain_partial(
        self, records: tuple[ProviderRawRecord, ...], pipeline
    ) -> ProviderPipelineResult:
        valid_rows: list[dict[str, object]] = []
        rejected: list[RejectedProviderRecord] = []
        for record in records:
            row = self.load((record,)).records[0]
            validation = pipeline.validator.validate((row,))
            if validation.is_valid:
                valid_rows.append(row)
                continue
            rejected.append(
                RejectedProviderRecord(
                    provider=record.source_provider,
                    chain=record.chain.value,
                    source_type=record.source_type,
                    tx_hash=record.tx_hash,
                    raw_reference=record.raw_reference,
                    reasons=tuple(
                        {
                            "field": issue.field,
                            "code": issue.code,
                            "message": issue.message,
                        }
                        for issue in validation.issues
                    ),
                )
            )
        batch = ImportBatch(
            Path("<provider>"),
            tuple(valid_rows),
            ColumnMapping({key: key for key in valid_rows[0]})
            if valid_rows
            else ColumnMapping({}),
        )
        return ProviderPipelineResult(
            pipeline.to_domain(batch),
            tuple(rejected),
        )
