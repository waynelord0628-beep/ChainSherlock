from datetime import UTC, datetime
from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
)
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


class EtherscanProvider(BaseProvider):
    chain = Chain.ETHEREUM
    name = "etherscan"
    requires_api_key = True
    capabilities = frozenset(
        {
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TRANSACTION,
            ProviderCapability.TOKEN_TRANSFERS,
            ProviderCapability.INTERNAL_TRANSACTIONS,
            ProviderCapability.BALANCE,
        }
    )

    def __init__(
        self,
        api_key: str,
        *,
        client: ProviderHttpClient | None = None,
        base_url: str = "https://api.etherscan.io/v2/api",
        limits: PaginationLimits | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.client = client or ProviderHttpClient(
            provider=self.name, chain=self.chain
        )
        self.limits = limits or PaginationLimits()

    async def health_check(self) -> HealthCheck:
        if not self.api_key:
            return HealthCheck(self.name, self.chain, False, "API key is not configured")
        try:
            await self._query(
                "balance",
                ProviderCapability.BALANCE,
                {"address": "0x0000000000000000000000000000000000000000"},
            )
            return HealthCheck(self.name, self.chain, True)
        except Exception:
            return HealthCheck(self.name, self.chain, False, "Provider unavailable")

    async def get_address_transactions(
        self, address: str, **kwargs
    ) -> ProviderResult:
        return await self._paged_account(
            address,
            action="txlist",
            capability=ProviderCapability.ADDRESS_TRANSACTIONS,
            source_type="normal_transaction",
            parser=self._parse_normal,
            **kwargs,
        )

    async def get_token_transfers(self, address: str, **kwargs) -> ProviderResult:
        return await self._paged_account(
            address,
            action="tokentx",
            capability=ProviderCapability.TOKEN_TRANSFERS,
            source_type="token_transfer",
            parser=self._parse_token,
            **kwargs,
        )

    async def get_internal_transactions(
        self, address: str, **kwargs
    ) -> ProviderResult:
        return await self._paged_account(
            address,
            action="txlistinternal",
            capability=ProviderCapability.INTERNAL_TRANSACTIONS,
            source_type="internal_transfer",
            parser=self._parse_internal,
            **kwargs,
        )

    async def get_transaction(self, tx_hash: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.TRANSACTION
        payload = await self.client.request_json(
            "GET",
            self.base_url,
            capability=capability,
            params={
                "chainid": "1",
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": tx_hash,
                "apikey": self.api_key,
            },
        )
        raw = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(raw, dict):
            return ProviderResult(
                self.name, self.chain, capability, (), Completeness.EMPTY
            )
        record = ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type="normal_transaction",
            tx_hash=raw.get("hash", tx_hash),
            block_number=int(raw["blockNumber"], 16) if raw.get("blockNumber") else None,
            from_address=raw.get("from"),
            to_address=raw.get("to"),
            asset_symbol="ETH",
            amount_raw=str(int(raw.get("value", "0x0"), 16)),
            decimals=18,
            success=None,
            transaction_type="native_transfer",
            metadata={"method_id": str(raw.get("input", ""))[:10]},
            raw_reference=f"transaction:{tx_hash}",
        )
        return ProviderResult(
            self.name, self.chain, capability, (record,), Completeness.COMPLETE, pages_fetched=1
        )

    async def get_balance(self, address: str, **kwargs) -> ProviderBalance:
        result = await self._query(
            "balance", ProviderCapability.BALANCE, {"address": address, "tag": "latest"}
        )
        return ProviderBalance(
            self.name, self.chain, address, str(result), 18, "ETH"
        )

    async def _paged_account(
        self,
        address: str,
        *,
        action: str,
        capability: ProviderCapability,
        source_type: str,
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
            page_size=page_size or self.limits.page_size,
        )

        async def fetch(cursor: str | None, size: int) -> ProviderPage:
            page_number = int(cursor or "1")
            rows = await self._query(
                action,
                capability,
                {
                    "address": address,
                    "startblock": 0,
                    "endblock": 999999999,
                    "page": page_number,
                    "offset": size,
                    "sort": "asc",
                },
            )
            if not isinstance(rows, list):
                self._response_error(capability, "Provider result must be a list")
            records = tuple(parser(item, source_type) for item in rows)
            next_cursor = str(page_number + 1) if len(rows) >= size else None
            return ProviderPage(records, next_cursor)

        return await paginate(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            fetch_page=fetch,
            limits=limits,
            ordering=ProviderOrdering.OLDEST_FIRST,
            pagination_strategy=PaginationStrategy.PAGE_NUMBER,
            stop_after=date_to,
            start_cursor=start_cursor,
        )

    async def _query(
        self,
        action: str,
        capability: ProviderCapability,
        parameters: dict[str, Any],
    ) -> Any:
        payload = await self.client.request_json(
            "GET",
            self.base_url,
            capability=capability,
            params={
                "chainid": "1",
                "module": "account",
                "action": action,
                **parameters,
                "apikey": self.api_key,
            },
        )
        if not isinstance(payload, dict):
            self._response_error(capability, "Provider envelope must be an object")
        status = str(payload.get("status", ""))
        result = payload.get("result")
        if status == "1":
            return result
        message = f"{payload.get('message', '')} {result if isinstance(result, str) else ''}".casefold()
        if "no transactions" in message or result == []:
            return []
        if "rate limit" in message or "max rate" in message:
            raise ProviderRateLimitError(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                safe_message="Provider rate limit reached",
                retryable=True,
                missing_data_category=capability.value,
            )
        if "api key" in message or "apikey" in message:
            raise ProviderAuthenticationError(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                safe_message="Provider authentication failed",
                missing_data_category=capability.value,
            )
        self._response_error(capability, "Provider returned an API error")

    def _response_error(self, capability: ProviderCapability, message: str):
        raise ProviderResponseError(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            safe_message=message,
            missing_data_category=capability.value,
        )

    def _parse_normal(self, item: dict[str, Any], source_type: str) -> ProviderRawRecord:
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type=source_type,
            tx_hash=item["hash"],
            block_number=self._int_or_none(item.get("blockNumber")),
            timestamp=self._unix_time(item.get("timeStamp")),
            from_address=item.get("from") or None,
            to_address=item.get("to") or None,
            asset_symbol="ETH",
            asset_contract=item.get("contractAddress") or None,
            amount_raw=str(item.get("value", "0")),
            decimals=18,
            success=str(item.get("isError", "0")) == "0",
            transaction_type="native_transfer",
            metadata={
                "method_id": item.get("methodId"),
                "confirmations": item.get("confirmations"),
                "fee": self._fee(item),
            },
            raw_reference=f"normal:{item['hash']}",
        )

    def _parse_token(self, item: dict[str, Any], source_type: str) -> ProviderRawRecord:
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type=source_type,
            tx_hash=item["hash"],
            block_number=self._int_or_none(item.get("blockNumber")),
            timestamp=self._unix_time(item.get("timeStamp")),
            from_address=item.get("from") or None,
            to_address=item.get("to") or None,
            asset_symbol=item.get("tokenSymbol") or None,
            asset_contract=item.get("contractAddress") or None,
            amount_raw=str(item.get("value", "0")),
            decimals=self._int_or_none(item.get("tokenDecimal")),
            success=True,
            transaction_type="token_transfer",
            metadata={
                "log_index": self._int_or_none(item.get("logIndex")),
                "confirmations": item.get("confirmations"),
            },
            raw_reference=f"token:{item['hash']}:{item.get('logIndex', '')}",
        )

    def _parse_internal(self, item: dict[str, Any], source_type: str) -> ProviderRawRecord:
        trace_id = item.get("traceId")
        return ProviderRawRecord(
            chain=self.chain,
            source_provider=self.name,
            source_type=source_type,
            tx_hash=item["hash"],
            block_number=self._int_or_none(item.get("blockNumber")),
            timestamp=self._unix_time(item.get("timeStamp")),
            from_address=item.get("from") or None,
            to_address=item.get("to") or None,
            asset_symbol="ETH",
            amount_raw=str(item.get("value", "0")),
            decimals=18,
            success=str(item.get("isError", "0")) == "0",
            transaction_type="internal_transfer",
            metadata={"trace_id": trace_id},
            raw_reference=f"internal:{item['hash']}:{trace_id or ''}",
        )

    @staticmethod
    def _unix_time(value: Any) -> datetime | None:
        return datetime.fromtimestamp(int(value), UTC) if value not in (None, "") else None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        return int(value) if value not in (None, "") else None

    @staticmethod
    def _fee(item: dict[str, Any]) -> str | None:
        if item.get("gasUsed") in (None, "") or item.get("gasPrice") in (None, ""):
            return None
        return str(int(item["gasUsed"]) * int(item["gasPrice"]))
