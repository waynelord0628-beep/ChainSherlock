from datetime import UTC, datetime

import pytest

from crypto_investigator.config import Settings
from crypto_investigator.core.pipeline import DataPipeline
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.importers.provider import ProviderRecordImporter
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.errors import ProviderUnavailableError
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderCapability,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.registry import ProviderRegistry
from crypto_investigator.providers.selection import ProviderSelectionPolicy


def settings() -> Settings:
    return Settings.model_validate(
        {
            "providers": {
                "ethereum": {"primary": "primary", "fallback": ["fallback"]},
                "tron": {"primary": "tron"},
                "bitcoin": {"primary": "bitcoin"},
            }
        }
    )


def raw(source_type: str = "normal_transaction", **metadata) -> ProviderRawRecord:
    return ProviderRawRecord(
        chain=Chain.ETHEREUM,
        source_provider="primary",
        source_type=source_type,
        tx_hash="0x" + "1" * 64,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        from_address="0x" + "a" * 40,
        to_address="0x" + "b" * 40,
        amount_raw="1000000000000000000",
        decimals=18,
        asset_symbol="ETH",
        transaction_type="native_transfer",
        metadata=metadata,
    )


class StubProvider(BaseProvider):
    chain = Chain.ETHEREUM
    capabilities = frozenset({ProviderCapability.ADDRESS_TRANSACTIONS})

    def __init__(self, name: str, fail: bool = False) -> None:
        self.name = name
        self.fail = fail

    async def health_check(self) -> HealthCheck:
        return HealthCheck(self.name, self.chain, not self.fail)

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        if self.fail:
            raise ProviderUnavailableError(
                provider=self.name,
                chain=self.chain,
                capability=ProviderCapability.ADDRESS_TRANSACTIONS,
                safe_message="unavailable",
                retryable=True,
            )
        return ProviderResult(
            self.name,
            self.chain,
            ProviderCapability.ADDRESS_TRANSACTIONS,
            (raw(),),
            Completeness.COMPLETE,
        )


def test_registry_registers_and_lists_provider() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary"))
    assert registry.get(Chain.ETHEREUM, "primary").name == "primary"
    assert registry.descriptors()[0].capabilities == (
        ProviderCapability.ADDRESS_TRANSACTIONS,
    )


def test_registry_rejects_duplicate_provider() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary"))
    with pytest.raises(ValueError):
        registry.register(StubProvider("primary"))


@pytest.mark.asyncio
async def test_registry_health_does_not_expose_configuration() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary"))
    descriptor = (await registry.health())[0]
    assert descriptor.health and descriptor.health.available


def test_selection_orders_primary_before_fallback() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary"))
    registry.register(StubProvider("fallback"))
    selected = ProviderSelectionPolicy(registry, settings()).candidates(
        Chain.ETHEREUM, ProviderCapability.ADDRESS_TRANSACTIONS
    )
    assert [provider.name for provider in selected] == ["primary", "fallback"]


def test_selection_honors_requested_provider() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary"))
    registry.register(StubProvider("fallback"))
    selected = ProviderSelectionPolicy(registry, settings()).candidates(
        Chain.ETHEREUM,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        requested="fallback",
    )
    assert selected[0].name == "fallback"


@pytest.mark.asyncio
async def test_collector_falls_back_and_retains_error() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider("primary", fail=True))
    registry.register(StubProvider("fallback"))
    result = await ProviderCollector(
        ProviderSelectionPolicy(registry, settings())
    ).collect_address(Chain.ETHEREUM, "0x" + "a" * 40)
    assert len(result.records) == 1
    assert len(result.errors) >= 1
    assert result.results[0].provider == "fallback"


def test_provider_importer_scales_raw_amount() -> None:
    batch = ProviderRecordImporter().load((raw(),))
    assert str(batch.records[0]["amount"]) == "1"


def test_provider_records_flow_through_existing_pipeline() -> None:
    batch = ProviderRecordImporter().load((raw(),))
    transactions = DataPipeline().to_domain(batch)
    assert len(transactions) == 1
    assert str(transactions[0].amount) == "1"


def test_distinct_token_logs_are_not_rejected_as_duplicate_hashes() -> None:
    records = (
        raw("token_transfer", log_index=1),
        raw("token_transfer", log_index=2),
    )
    transactions = DataPipeline().to_domain(ProviderRecordImporter().load(records))
    assert len(transactions) == 2


def test_empty_provider_batch_is_valid() -> None:
    assert DataPipeline().to_domain(ProviderRecordImporter().load(())) == ()
