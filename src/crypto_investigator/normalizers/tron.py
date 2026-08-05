from dataclasses import replace
from collections.abc import Mapping
from typing import Any

from crypto_investigator.domain.transaction import Chain, TransactionType
from crypto_investigator.normalizers.base import BaseNormalizer


class TronNormalizer(BaseNormalizer):
    chain = Chain.TRON

    def normalize(self, record: Mapping[str, Any]):
        transaction = super().normalize(record)
        source_metadata = record.get("source_metadata")
        provider_metadata = (
            source_metadata if isinstance(source_metadata, Mapping) else {}
        )
        contract_type = str(
            record.get("contract_type")
            or provider_metadata.get("contract_type")
            or ""
        ).strip()
        symbol = str(record.get("asset_symbol") or "").strip()

        if contract_type == "TransferContract" and symbol.upper() == "TRX":
            return replace(
                transaction,
                asset_symbol="TRX",
                transaction_type=TransactionType.NATIVE_TRANSFER,
            )
        if contract_type == "TransferAssetContract":
            return replace(
                transaction,
                asset_symbol=symbol or "unknown_tron_asset",
                transaction_type=TransactionType.TOKEN_TRANSFER,
            )
        if transaction.transaction_type is TransactionType.TOKEN_TRANSFER:
            return replace(
                transaction,
                asset_symbol=symbol or "unknown_tron_asset",
            )
        if symbol.upper() == "TRX":
            return replace(
                transaction,
                asset_symbol="unknown_tron_asset",
                transaction_type=TransactionType.UNKNOWN,
            )
        return replace(
            transaction,
            asset_symbol=symbol or "unknown_tron_asset",
        )

    def normalize_address(self, value: Any) -> str | None:
        return self._optional_text(value)
