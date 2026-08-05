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
    PaginationMetadata,
)
from crypto_investigator.providers.models import PaginationStrategy, ProviderOrdering
from crypto_investigator.providers.pagination import PaginationLimits, paginate


class BlockstreamProvider(BaseProvider):
    chain = Chain.BITCOIN
    name = "blockstream"
    capabilities = frozenset(
        {
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TRANSACTION,
            ProviderCapability.BALANCE,
            ProviderCapability.UTXO,
        }
    )

    def __init__(
        self,
        *,
        client: ProviderHttpClient | None = None,
        base_url: str = "https://blockstream.info/api",
        limits: PaginationLimits | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = client or ProviderHttpClient(
            provider=self.name, chain=self.chain
        )
        self.limits = limits or PaginationLimits(page_size=25)

    async def health_check(self) -> HealthCheck:
        try:
            await self.client.request_json(
                "GET",
                f"{self.base_url}/blocks",
                capability=ProviderCapability.ADDRESS_TRANSACTIONS,
            )
            return HealthCheck(self.name, self.chain, True)
        except Exception:
            return HealthCheck(self.name, self.chain, False, "Provider unavailable")

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.ADDRESS_TRANSACTIONS
        limits = PaginationLimits(
            max_pages=(
                None
                if kwargs.get("unbounded")
                else kwargs.get("max_pages") or self.limits.max_pages
            ),
            max_records=(
                None
                if kwargs.get("unbounded")
                else kwargs.get("max_records") or self.limits.max_records
            ),
            page_size=25,
        )

        async def fetch(cursor: str | None, size: int) -> ProviderPage:
            endpoint = (
                f"{self.base_url}/address/{address}/txs"
                if cursor is None
                else f"{self.base_url}/address/{address}/txs/chain/{cursor}"
            )
            payload = await self.client.request_json(
                "GET", endpoint, capability=capability
            )
            if not isinstance(payload, list):
                self._response_error(capability, "Esplora transactions must be a list")
            records = tuple(
                record
                for item in payload
                for record in self._parse_transaction(
                    item, target_address=address
                )
            )
            next_cursor = payload[-1].get("txid") if len(payload) >= 25 else None
            return ProviderPage(records, next_cursor)

        return await paginate(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            fetch_page=fetch,
            limits=limits,
            ordering=ProviderOrdering.NEWEST_FIRST,
            pagination_strategy=PaginationStrategy.BEFORE_TXID,
            stop_before=kwargs.get("date_from"),
            start_cursor=kwargs.get("start_cursor"),
        )

    async def get_transaction(self, tx_hash: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.TRANSACTION
        payload = await self.client.request_json(
            "GET", f"{self.base_url}/tx/{tx_hash}", capability=capability
        )
        if not isinstance(payload, dict):
            self._response_error(capability, "Esplora transaction must be an object")
        records = self._parse_transaction(payload)
        return ProviderResult(
            self.name,
            self.chain,
            capability,
            records,
            Completeness.COMPLETE if records else Completeness.EMPTY,
            pages_fetched=1,
            fetched_records=len(records),
            pagination=PaginationMetadata(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                ordering=ProviderOrdering.PROVIDER_DEFINED,
                pagination_strategy=PaginationStrategy.PROVIDER_DEFINED,
                pagination_complete=True,
                fetched_records=len(records),
                accepted_records=len(records),
                completeness=(
                    Completeness.COMPLETE if records else Completeness.EMPTY
                ),
            ),
        )

    async def get_utxos(self, address: str, **kwargs) -> ProviderResult:
        capability = ProviderCapability.UTXO
        payload = await self.client.request_json(
            "GET", f"{self.base_url}/address/{address}/utxo", capability=capability
        )
        if not isinstance(payload, list):
            self._response_error(capability, "Esplora UTXO result must be a list")
        records = tuple(
            ProviderRawRecord(
                chain=self.chain,
                source_provider=self.name,
                source_type="bitcoin_output",
                tx_hash=item["txid"],
                block_number=(item.get("status") or {}).get("block_height"),
                to_address=address,
                asset_symbol="BTC",
                amount_raw=str(item.get("value", 0)),
                decimals=8,
                success=True,
                transaction_type="utxo_transfer",
                metadata={
                    "output_index": item.get("vout"),
                    "utxo": True,
                    "confirmed": (item.get("status") or {}).get("confirmed", False),
                },
                raw_reference=f"utxo:{item['txid']}:{item.get('vout')}",
            )
            for item in payload
        )
        return ProviderResult(
            self.name,
            self.chain,
            capability,
            records,
            Completeness.COMPLETE if records else Completeness.EMPTY,
            pages_fetched=1,
            fetched_records=len(records),
            pagination=PaginationMetadata(
                provider=self.name,
                chain=self.chain,
                capability=capability,
                ordering=ProviderOrdering.PROVIDER_DEFINED,
                pagination_strategy=PaginationStrategy.PROVIDER_DEFINED,
                pagination_complete=True,
                fetched_records=len(records),
                accepted_records=len(records),
                completeness=(
                    Completeness.COMPLETE if records else Completeness.EMPTY
                ),
            ),
        )

    async def get_balance(self, address: str, **kwargs) -> ProviderBalance:
        capability = ProviderCapability.BALANCE
        payload = await self.client.request_json(
            "GET", f"{self.base_url}/address/{address}", capability=capability
        )
        if not isinstance(payload, dict):
            self._response_error(capability, "Esplora address result must be an object")
        chain = payload.get("chain_stats") or {}
        mempool = payload.get("mempool_stats") or {}
        funded = int(chain.get("funded_txo_sum", 0)) + int(mempool.get("funded_txo_sum", 0))
        spent = int(chain.get("spent_txo_sum", 0)) + int(mempool.get("spent_txo_sum", 0))
        return ProviderBalance(self.name, self.chain, address, str(funded - spent), 8, "BTC")

    def _parse_transaction(
        self,
        item: dict[str, Any],
        *,
        target_address: str | None = None,
    ) -> tuple[ProviderRawRecord, ...]:
        tx_hash = item["txid"]
        status = item.get("status") or {}
        inputs = item.get("vin") or []
        outputs = item.get("vout") or []
        source_addresses = [
            (entry.get("prevout") or {}).get("scriptpubkey_address")
            for entry in inputs
            if entry.get("prevout")
        ]
        target_is_source = bool(
            target_address
            and any(
                value == target_address
                for value in source_addresses
                if value
            )
        )
        first_source = (
            target_address
            if target_is_source
            else next((value for value in source_addresses if value), None)
        )
        timestamp = (
            datetime.fromtimestamp(status["block_time"], UTC)
            if status.get("block_time")
            else None
        )
        return tuple(
            ProviderRawRecord(
                chain=self.chain,
                source_provider=self.name,
                source_type="bitcoin_output",
                tx_hash=tx_hash,
                block_number=status.get("block_height"),
                timestamp=timestamp,
                from_address=first_source,
                to_address=output.get("scriptpubkey_address"),
                asset_symbol="BTC",
                amount_raw=str(output.get("value", 0)),
                decimals=8,
                success=True,
                transaction_type="utxo_transfer",
                metadata={
                    "output_index": index,
                    "fee": item.get("fee"),
                    "confirmed": status.get("confirmed", False),
                    "inputs": inputs,
                    "outputs": outputs,
                },
                raw_reference=f"output:{tx_hash}:{index}",
            )
            for index, output in enumerate(outputs)
            if output.get("scriptpubkey_address")
            and (
                target_address is None
                or target_is_source
                or output.get("scriptpubkey_address") == target_address
            )
        )

    def _response_error(self, capability: ProviderCapability, message: str):
        raise ProviderResponseError(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            safe_message=message,
            missing_data_category=capability.value,
        )
