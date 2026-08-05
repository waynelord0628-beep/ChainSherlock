from datetime import UTC, datetime
from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.errors import ProviderResponseError
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderBalance,
    ProviderCapability,
    ProviderPage,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.models import PaginationStrategy, ProviderOrdering
from crypto_investigator.providers.pagination import PaginationLimits, paginate
from crypto_investigator.utils.tron import tron_address_to_base58


class TronGridProvider(BaseProvider):
    chain = Chain.TRON
    name = "trongrid"
    requires_api_key = False
    capabilities = frozenset(
        {
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TRANSACTION,
            ProviderCapability.TOKEN_TRANSFERS,
            ProviderCapability.BALANCE,
        }
    )

    def __init__(
        self,
        api_key: str = "",
        *,
        client: ProviderHttpClient | None = None,
        base_url: str = "https://api.trongrid.io",
        limits: PaginationLimits | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = client or ProviderHttpClient(
            provider=self.name, chain=self.chain
        )
        self.limits = limits or PaginationLimits(page_size=200)

    @property
    def headers(self) -> dict[str, str] | None:
        return {"TRON-PRO-API-KEY": self.api_key} if self.api_key else None

    async def health_check(self) -> HealthCheck:
        try:
            await self.client.request_json(
                "GET",
                f"{self.base_url}/wallet/getnowblock",
                capability=ProviderCapability.ADDRESS_TRANSACTIONS,
                headers=self.headers,
            )
            return HealthCheck(self.name, self.chain, True)
        except Exception:
            return HealthCheck(self.name, self.chain, False, "Provider unavailable")

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        return await self._paged(
            address,
            "transactions",
            ProviderCapability.ADDRESS_TRANSACTIONS,
            self._parse_trx,
            **kwargs,
        )

    async def get_token_transfers(self, address: str, **kwargs) -> ProviderResult:
        return await self._paged(
            address,
            "transactions/trc20",
            ProviderCapability.TOKEN_TRANSFERS,
            self._parse_trc20,
            **kwargs,
        )

    async def get_transaction(self, tx_hash: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.TRANSACTION
        item = await self.client.request_json(
            "POST",
            f"{self.base_url}/wallet/gettransactionbyid",
            capability=capability,
            json={"value": tx_hash},
            headers=self.headers,
        )
        if not isinstance(item, dict) or not item.get("txID"):
            return ProviderResult(self.name, self.chain, capability, (), Completeness.EMPTY)
        record = self._parse_trx(item)
        return ProviderResult(
            self.name, self.chain, capability, (record,), Completeness.COMPLETE, pages_fetched=1
        )

    async def get_balance(self, address: str, **kwargs) -> ProviderBalance:
        capability = ProviderCapability.BALANCE
        payload = await self.client.request_json(
            "GET",
            f"{self.base_url}/v1/accounts/{address}",
            capability=capability,
            headers=self.headers,
        )
        rows = payload.get("data") if isinstance(payload, dict) else None
        balance = rows[0].get("balance", 0) if rows else 0
        return ProviderBalance(self.name, self.chain, address, str(balance), 6, "TRX")

    async def _paged(
        self,
        address: str,
        endpoint: str,
        capability: ProviderCapability,
        parser,
        max_pages: int | None = None,
        max_records: int | None = None,
        page_size: int | None = None,
        unbounded: bool = False,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        start_cursor: str | None = None,
    ) -> ProviderResult:
        limits = PaginationLimits(
            max_pages=None if unbounded else max_pages or self.limits.max_pages,
            max_records=None if unbounded else max_records or self.limits.max_records,
            page_size=min(page_size or self.limits.page_size, 200),
        )

        async def fetch(cursor: str | None, size: int) -> ProviderPage:
            params: dict[str, Any] = {"limit": size}
            if cursor:
                params["fingerprint"] = cursor
            payload = await self.client.request_json(
                "GET",
                f"{self.base_url}/v1/accounts/{address}/{endpoint}",
                capability=capability,
                params=params,
                headers=self.headers,
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
                raise ProviderResponseError(
                    provider=self.name,
                    chain=self.chain,
                    capability=capability,
                    safe_message="TronGrid data must be a list",
                    missing_data_category=capability.value,
                )
            records = tuple(parser(item) for item in payload.get("data", []))
            next_cursor = (payload.get("meta") or {}).get("fingerprint")
            return ProviderPage(records, next_cursor)

        return await paginate(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            fetch_page=fetch,
            limits=limits,
            ordering=ProviderOrdering.NEWEST_FIRST,
            pagination_strategy=PaginationStrategy.FINGERPRINT,
            stop_before=date_from,
            start_cursor=start_cursor,
        )

    def _parse_trx(self, item: dict[str, Any]) -> ProviderRawRecord:
        contracts = (item.get("raw_data") or {}).get("contract") or []
        contract = contracts[0] if contracts else {}
        contract_type = contract.get("type", "unknown")
        value = ((contract.get("parameter") or {}).get("value") or {})
        owner = self._address(value.get("owner_address"))
        recipient = self._address(value.get("to_address"))
        if contract_type == "TransferContract":
            asset_symbol = "TRX"
            transaction_type = "native_transfer"
        elif contract_type == "TransferAssetContract":
            asset_symbol = self._asset_identifier(value.get("asset_name"))
            transaction_type = "token_transfer"
        else:
            asset_symbol = "unknown_tron_asset"
            transaction_type = "unknown"
        success = all(
            result.get("contractRet") == "SUCCESS"
            for result in item.get("ret", [])
        ) if item.get("ret") else None
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type="normal_transaction",
            tx_hash=item["txID"],
            timestamp=self._millis(item.get("block_timestamp") or (item.get("raw_data") or {}).get("timestamp")),
            from_address=owner,
            to_address=recipient,
            asset_symbol=asset_symbol,
            amount_raw=str(value.get("amount", "0")),
            decimals=6,
            success=success,
            transaction_type=transaction_type,
            metadata={"contract_type": contract_type},
            raw_reference=f"trx:{item['txID']}",
        )

    @staticmethod
    def _asset_identifier(value: Any) -> str:
        if value is None:
            return "unknown_tron_asset"
        if isinstance(value, bytes):
            try:
                decoded = value.decode("utf-8").strip()
            except UnicodeDecodeError:
                decoded = ""
            return decoded or "unknown_tron_asset"
        text = str(value).strip()
        if not text:
            return "unknown_tron_asset"
        try:
            if len(text) % 2 == 0:
                decoded = bytes.fromhex(text).decode("utf-8").strip()
                if decoded:
                    return decoded
        except (ValueError, UnicodeDecodeError):
            pass
        return text

    def _parse_trc20(self, item: dict[str, Any]) -> ProviderRawRecord:
        token = item.get("token_info") or {}
        tx_hash = item.get("transaction_id")
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type="token_transfer",
            tx_hash=tx_hash,
            timestamp=self._millis(item.get("block_timestamp")),
            from_address=self._address(item.get("from")),
            to_address=self._address(item.get("to")),
            asset_symbol=token.get("symbol"),
            asset_contract=self._address(token.get("address")),
            amount_raw=str(item.get("value", "0")),
            decimals=int(token.get("decimals") or 0),
            success=True,
            transaction_type="token_transfer",
            metadata={"log_index": item.get("event_index")},
            raw_reference=f"trc20:{tx_hash}:{item.get('event_index', '')}",
        )

    @staticmethod
    def _address(value: Any) -> str | None:
        return tron_address_to_base58(str(value)) if value else None

    @staticmethod
    def _millis(value: Any) -> datetime | None:
        return datetime.fromtimestamp(int(value) / 1000, UTC) if value else None
