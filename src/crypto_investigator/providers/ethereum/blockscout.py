from datetime import datetime
import json
from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.errors import ProviderResponseError
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderCapability,
    ProviderPage,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.models import PaginationStrategy, ProviderOrdering
from crypto_investigator.providers.pagination import PaginationLimits, paginate


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
        limits: PaginationLimits | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or ProviderHttpClient(
            provider=self.name, chain=self.chain
        )
        self.limits = limits or PaginationLimits(page_size=50)

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
        return await self._paginate(
            address, "transactions", capability, self._parse_transaction, kwargs
        )

    async def get_token_transfers(self, address: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.TOKEN_TRANSFERS
        return await self._paginate(
            address, "token-transfers", capability, self._parse_token, kwargs
        )

    async def _paginate(
        self, address: str, endpoint: str, capability, parser, options
    ) -> ProviderResult:
        limits = PaginationLimits(
            max_pages=(
                None
                if options.get("unbounded")
                else options.get("max_pages") or self.limits.max_pages
            ),
            max_records=(
                None
                if options.get("unbounded")
                else options.get("max_records") or self.limits.max_records
            ),
            page_size=self.limits.page_size,
        )

        async def fetch(cursor: str | None, size: int) -> ProviderPage:
            params = json.loads(cursor) if cursor else {}
            payload = await self.client.request_json(
                "GET",
                f"{self.base_url}/api/v2/addresses/{address}/{endpoint}",
                capability=capability,
                params=params or None,
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
            next_params = payload.get("next_page_params")
            next_cursor = (
                json.dumps(next_params, sort_keys=True) if next_params else None
            )
            return ProviderPage(tuple(parser(item) for item in items), next_cursor)

        return await paginate(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            fetch_page=fetch,
            limits=limits,
            ordering=ProviderOrdering.NEWEST_FIRST,
            pagination_strategy=PaginationStrategy.CURSOR,
            stop_before=options.get("date_from"),
            start_cursor=options.get("start_cursor"),
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
