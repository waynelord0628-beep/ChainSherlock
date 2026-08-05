from collections import defaultdict
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import json
from pathlib import Path

from crypto_investigator.domain.transaction import Transaction
from crypto_investigator.analysis_materiality import (
    DEFAULT_TRX_DUST_THRESHOLD,
    classify_trc10_symbol,
    split_material_transactions,
)


class TronAssetCandidateClassification(StrEnum):
    ADVERTISEMENT_TOKEN_CANDIDATE = "advertisement_token_candidate"
    SPAM_TOKEN_CANDIDATE = "spam_token_candidate"
    UNKNOWN_TRC10_ASSET = "unknown_trc10_asset"


@dataclass(frozen=True, slots=True)
class TronOtherAssetTransfer:
    tx_hash: str
    timestamp: datetime | None
    from_address: str | None
    to_address: str | None
    value: Decimal
    symbol: str
    asset_identifier: str
    contract_type: str
    status: str
    candidate_classification: TronAssetCandidateClassification
    reason_codes: tuple[str, ...]
    confidence: str
    review_status: str = "not_reviewed"


def classify_tron_other_asset(transaction: Transaction) -> TronOtherAssetTransfer:
    metadata = transaction.metadata or {}
    contract_type = str(metadata.get("contract_type") or "")
    if contract_type != "TransferAssetContract":
        raise ValueError("TRC10 classifier requires TransferAssetContract")
    symbol = str(transaction.asset_symbol or "unknown_tron_asset").strip()
    reasons = ["transfer_asset_contract", "not_native_trx"]
    category, reason, confidence = classify_trc10_symbol(symbol)
    classification = TronAssetCandidateClassification(category)
    reasons.append(reason)
    return TronOtherAssetTransfer(
        tx_hash=transaction.tx_hash,
        timestamp=transaction.timestamp,
        from_address=transaction.from_address,
        to_address=transaction.to_address,
        value=transaction.amount or Decimal(0),
        symbol=symbol,
        asset_identifier=symbol,
        contract_type=contract_type,
        status="SUCCESS" if transaction.success is True else "UNKNOWN",
        candidate_classification=classification,
        reason_codes=tuple(reasons),
        confidence=confidence,
    )


def other_asset_transfers(
    transactions: tuple[Transaction, ...],
) -> tuple[TronOtherAssetTransfer, ...]:
    return tuple(
        classify_tron_other_asset(transaction)
        for transaction in transactions
        if str((transaction.metadata or {}).get("contract_type") or "")
        == "TransferAssetContract"
    )


def summarize_other_assets(
    transfers: tuple[TronOtherAssetTransfer, ...],
) -> tuple[dict[str, object], ...]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "transaction_count": 0,
            "incoming_amount": Decimal(0),
            "source_addresses": set(),
            "classifications": set(),
            "confidences": set(),
        }
    )
    for transfer in transfers:
        item = grouped[transfer.symbol]
        item["transaction_count"] += 1
        item["incoming_amount"] += transfer.value
        if transfer.from_address:
            item["source_addresses"].add(transfer.from_address)
        item["classifications"].add(transfer.candidate_classification.value)
        item["confidences"].add(transfer.confidence)
    return tuple(
        {
            "symbol": symbol,
            "transaction_count": values["transaction_count"],
            "incoming_amount": str(values["incoming_amount"]),
            "source_address_count": len(values["source_addresses"]),
            "candidate_classification": sorted(values["classifications"])[0],
            "confidence": sorted(values["confidences"])[0],
            "review_status": "not_reviewed",
        }
        for symbol, values in sorted(
            grouped.items(),
            key=lambda item: (-item[1]["transaction_count"], item[0]),
        )
    )


def write_tron_other_asset_artifacts(
    transactions: tuple[Transaction, ...],
    output_directory: Path,
) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    transfers = other_asset_transfers(transactions)
    csv_path = output_directory / "trc10_other_asset_transfers.csv"
    columns = (
        "tx_hash",
        "timestamp",
        "from_address",
        "to_address",
        "value",
        "symbol",
        "asset_identifier",
        "contract_type",
        "status",
        "candidate_classification",
        "reason_codes",
        "confidence",
        "review_status",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for transfer in transfers:
            row = asdict(transfer)
            row["timestamp"] = (
                transfer.timestamp.isoformat() if transfer.timestamp else ""
            )
            row["candidate_classification"] = (
                transfer.candidate_classification.value
            )
            row["reason_codes"] = "|".join(transfer.reason_codes)
            writer.writerow(row)
    summary_path = output_directory / "trc10_other_asset_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_type": "TRC10/Other Asset Transfers",
                "transaction_count": len(transfers),
                "native_trx_transaction_count": 0,
                "assets": summarize_other_assets(transfers),
                "review_status": "not_reviewed",
                "limitations": [
                    "候選分類不代表已確認為詐騙或釣魚。",
                    "原始 Evidence 未修改，所有分類均可人工覆核。",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"transfers": csv_path, "summary": summary_path}


def write_trx_dust_exclusions(
    transactions: tuple[Transaction, ...],
    output_directory: Path,
    *,
    threshold: Decimal = DEFAULT_TRX_DUST_THRESHOLD,
) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    _material, exclusions = split_material_transactions(
        transactions,
        trx_dust_threshold=threshold,
    )
    dust = tuple(
        item
        for item in exclusions
        if item.rule == "native_trx_below_materiality_threshold"
    )
    path = output_directory / "dust_exclusions.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "tx_hash",
                "timestamp",
                "from_address",
                "to_address",
                "amount",
                "asset",
                "materiality_threshold",
                "exclusion_rule",
                "reversible",
                "review_status",
            )
        )
        for item in dust:
            transaction = item.transaction
            writer.writerow(
                (
                    transaction.tx_hash,
                    transaction.timestamp.isoformat()
                    if transaction.timestamp
                    else "",
                    transaction.from_address or "",
                    transaction.to_address or "",
                    str(transaction.amount or Decimal(0)),
                    transaction.asset_symbol or "",
                    str(threshold),
                    item.rule,
                    item.reversible,
                    item.review_status,
                )
            )
    return path
