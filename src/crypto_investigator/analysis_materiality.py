from dataclasses import dataclass
from decimal import Decimal
import re

from crypto_investigator.domain.transaction import Transaction, TransactionType


DEFAULT_TRX_DUST_THRESHOLD = Decimal("0.0001")
_ADVERTISEMENT_TEXT = re.compile(
    r"(?:\.|com|ink|ads?|energy|gas|hash|pay|game|fee|buy)",
    re.IGNORECASE,
)


def classify_trc10_symbol(symbol: str | None) -> tuple[str, str, str]:
    value = str(symbol or "").strip()
    if not value or value == "unknown_tron_asset":
        return "unknown_trc10_asset", "asset_identifier_missing", "high"
    if _ADVERTISEMENT_TEXT.search(value):
        return (
            "advertisement_token_candidate",
            "advertising_style_symbol",
            "medium",
        )
    if value.isdecimal():
        return "spam_token_candidate", "numeric_trc10_identifier", "medium"
    return "unknown_trc10_asset", "unverified_trc10_asset", "low"


@dataclass(frozen=True, slots=True)
class MaterialityExclusion:
    transaction: Transaction
    rule: str
    reversible: bool = True
    review_status: str = "not_reviewed"


def split_material_transactions(
    transactions: tuple[Transaction, ...],
    *,
    trx_dust_threshold: Decimal = DEFAULT_TRX_DUST_THRESHOLD,
) -> tuple[tuple[Transaction, ...], tuple[MaterialityExclusion, ...]]:
    material = []
    exclusions = []
    for transaction in transactions:
        metadata = transaction.metadata or {}
        contract_type = str(metadata.get("contract_type") or "")
        if contract_type == "TransferAssetContract":
            exclusions.append(
                MaterialityExclusion(
                    transaction,
                    "trc10_or_other_asset_not_native_trx",
                )
            )
            continue
        if (
            transaction.asset_symbol == "TRX"
            and contract_type == "TransferContract"
            and transaction.transaction_type is TransactionType.NATIVE_TRANSFER
            and transaction.amount is not None
            and abs(transaction.amount) < trx_dust_threshold
        ):
            exclusions.append(
                MaterialityExclusion(
                    transaction,
                    "native_trx_below_materiality_threshold",
                )
            )
            continue
        material.append(transaction)
    return tuple(material), tuple(exclusions)
