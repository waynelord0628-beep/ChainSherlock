from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from crypto_investigator.importers.base import ImportBatch
from crypto_investigator.importers.mapping import ColumnMapping
from crypto_investigator.providers.models import ProviderRawRecord


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
