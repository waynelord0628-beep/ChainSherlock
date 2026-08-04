from dataclasses import dataclass

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.dedup import deduplicate_records
from crypto_investigator.providers.errors import ProviderError
from crypto_investigator.providers.models import (
    Completeness,
    ProviderCapability,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.selection import ProviderSelectionPolicy


@dataclass(frozen=True, slots=True)
class CollectionResult:
    records: tuple[ProviderRawRecord, ...]
    results: tuple[ProviderResult, ...]
    errors: tuple[ProviderError, ...]


class ProviderCollector:
    def __init__(self, policy: ProviderSelectionPolicy) -> None:
        self.policy = policy

    async def collect_address(
        self,
        chain: Chain,
        address: str,
        *,
        provider: str | None = None,
    ) -> CollectionResult:
        capabilities = [ProviderCapability.ADDRESS_TRANSACTIONS]
        if chain in (Chain.ETHEREUM, Chain.TRON):
            capabilities.append(ProviderCapability.TOKEN_TRANSFERS)
        if chain is Chain.ETHEREUM:
            capabilities.append(ProviderCapability.INTERNAL_TRANSACTIONS)
        return await self._collect(chain, address, tuple(capabilities), provider)

    async def collect_transaction(
        self,
        chain: Chain,
        tx_hash: str,
        *,
        provider: str | None = None,
    ) -> CollectionResult:
        return await self._collect(
            chain, tx_hash, (ProviderCapability.TRANSACTION,), provider
        )

    async def _collect(
        self,
        chain: Chain,
        identifier: str,
        capabilities: tuple[ProviderCapability, ...],
        requested: str | None,
    ) -> CollectionResult:
        results: list[ProviderResult] = []
        errors: list[ProviderError] = []
        for capability in capabilities:
            try:
                candidates = self.policy.candidates(chain, capability, requested)
            except ProviderError as error:
                errors.append(error)
                continue
            for candidate in candidates:
                try:
                    method_name = {
                        ProviderCapability.ADDRESS_TRANSACTIONS: "get_address_transactions",
                        ProviderCapability.TRANSACTION: "get_transaction",
                        ProviderCapability.TOKEN_TRANSFERS: "get_token_transfers",
                        ProviderCapability.INTERNAL_TRANSACTIONS: "get_internal_transactions",
                    }[capability]
                    result = await getattr(candidate, method_name)(identifier)
                    results.append(result)
                    break
                except ProviderError as error:
                    errors.append(error)
        records = deduplicate_records(
            record for result in results for record in result.records
        )
        return CollectionResult(records, tuple(results), tuple(errors))
