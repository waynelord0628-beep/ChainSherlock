from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from crypto_investigator.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class ExportPaths:
    transactions_csv: Path
    summary_json: Path


class TransactionExporter:
    """Export normalized domain transactions without performing analysis."""

    columns = (
        "chain",
        "tx_hash",
        "timestamp",
        "block_number",
        "from_address",
        "to_address",
        "asset_symbol",
        "asset_contract",
        "amount",
        "decimals",
        "direction",
        "transaction_type",
        "metadata",
    )

    def export(
        self,
        transactions: tuple[Transaction, ...],
        output_dir: Path,
        source: Path,
    ) -> ExportPaths:
        output_dir.mkdir(parents=True, exist_ok=True)
        transactions_path = output_dir / "transactions_normalized.csv"
        summary_path = output_dir / "summary.json"

        rows = [self._to_row(transaction) for transaction in transactions]
        pd.DataFrame(rows, columns=self.columns).to_csv(
            transactions_path,
            index=False,
            encoding="utf-8",
        )
        summary = {
            "source": str(source),
            "transaction_count": len(transactions),
            "chains": dict(sorted(Counter(tx.chain.value for tx in transactions).items())),
            "assets": dict(
                sorted(
                    Counter(tx.asset_symbol for tx in transactions if tx.asset_symbol).items()
                )
            ),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return ExportPaths(transactions_path, summary_path)

    @staticmethod
    def _to_row(transaction: Transaction) -> dict[str, object]:
        return {
            "chain": transaction.chain.value,
            "tx_hash": transaction.tx_hash,
            "timestamp": transaction.timestamp.isoformat() if transaction.timestamp else None,
            "block_number": transaction.block_number,
            "from_address": transaction.from_address,
            "to_address": transaction.to_address,
            "asset_symbol": transaction.asset_symbol,
            "asset_contract": transaction.asset_contract,
            "amount": str(transaction.amount) if transaction.amount is not None else None,
            "decimals": transaction.decimals,
            "direction": transaction.direction.value,
            "transaction_type": transaction.transaction_type.value,
            "metadata": json.dumps(dict(transaction.metadata), ensure_ascii=False, default=str),
        }
