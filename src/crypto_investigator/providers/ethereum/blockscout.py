from datetime import datetime
from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.errors import ProviderResponseError
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderCapability,
    ProviderRawRecord,
    ProviderResult,
)


class BlockscoutProvider(BaseProvider):
    chain = Chain.ETHEREUM
    name = "blockscout"
    capabilities = frozenset(
        {
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TOKEN_TRANSFERS,
        }
    )

    def __init__(
        self,
        base_url: str,
        *,
        client: ProviderHttpClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or ProviderHttpClient(
            provider=self.name, chain=self.chain
        )

    async def health_check(self) -> HealthCheck:
        try:
            await self.client.request_json(
                "GET",
                f"{self.base_url}/api/v2/stats",
                capability=ProviderCapability.ADDRESS_TRANSACTIONS,
            )
            return HealthCheck(self.name, self.chain, True)
        except Exception:
            return HealthCheck(self.name, self.chain, False, "Provider unavailable")

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.ADDRESS_TRANSACTIONS
        payload = await self.client.request_json(
            "GET",
            f"{self.base_url}/api/v2/addresses/{address}/transactions",
            capability=capability,
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise ProviderResponseError(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                safe_message="Blockscout items must be a list",
                missing_data_category=capability.value,
            )
        records = tuple(self._parse_transaction(item) for item in items)
        warnings = (
            ("Additional Blockscout pages are available but not fetched",)
            if payload.get("next_page_params")
            else ()
        )
        return ProviderResult(
            self.name,
            self.chain,
            capability,
            records,
            Completeness.PARTIAL if warnings else (Completeness.COMPLETE if records else Completeness.EMPTY),
            warnings=warnings,
            pages_fetched=1,
        )

    async def get_token_transfers(self, address: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.TOKEN_TRANSFERS
        payload = await self.client.request_json(
            "GET",
            f"{self.base_url}/api/v2/addresses/{address}/token-transfers",
            capability=capability,
        )
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise ProviderResponseError(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                safe_message="Blockscout items must be a list",
                missing_data_category=capability.value,
            )
        records = tuple(self._parse_token(item) for item in items)
        return ProviderResult(
            self.name,
            self.chain,
            capability,
            records,
            Completeness.COMPLETE if records else Completeness.EMPTY,
            pages_fetched=1,
        )

    def _parse_transaction(self, item: dict[str, Any]) -> ProviderRawRecord:
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type="normal_transaction",
            tx_hash=item["hash"],
            block_number=item.get("block_number"),
            timestamp=self._time(item.get("timestamp")),
            from_address=self._address(item.get("from")),
            to_address=self._address(item.get("to")),
            asset_symbol="ETH",
            amount_raw=str(item.get("value", "0")),
            decimals=18,
            success=item.get("status") == "ok",
            transaction_type="native_transfer",
            metadata={
                "method_id": item.get("method"),
                "confirmations": item.get("confirmations"),
                "fee": (item.get("fee") or {}).get("value"),
            },
            raw_reference=f"normal:{item['hash']}",
        )

    def _parse_token(self, item: dict[str, Any]) -> ProviderRawRecord:
        token = item.get("token") or {}
        total = item.get("total") or {}
        tx_hash = item.get("transaction_hash")
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type="token_transfer",
            tx_hash=tx_hash,
            timestamp=self._time(item.get("timestamp")),
            from_address=self._address(item.get("from")),
            to_address=self._address(item.get("to")),
            asset_symbol=token.get("symbol"),
            asset_contract=token.get("address_hash"),
            amount_raw=str(total.get("value", "0")),
            decimals=int(total.get("decimals") or token.get("decimals") or 0),
            success=True,
            transaction_type="token_transfer",
            metadata={"log_index": item.get("log_index")},
            raw_reference=f"token:{tx_hash}:{item.get('log_index', '')}",
        )

    @staticmethod
    def _address(value: Any) -> str | None:
        return value.get("hash") if isinstance(value, dict) else value

    @staticmethod
    def _time(value: Any) -> datetime | None:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
