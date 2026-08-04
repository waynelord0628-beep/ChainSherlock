from datetime import UTC, datetime

import pytest

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.config import Settings
from crypto_investigator.core.pipeline import DataPipeline, PipelineValidationError
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.importers.provider import ProviderRecordImporter
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.errors import ProviderAuthenticationError
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderCapability,
    ProviderPage,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.pagination import PaginationLimits, paginate
from crypto_investigator.providers.registry import ProviderRegistry
from crypto_investigator.providers.selection import ProviderSelectionPolicy


ADDRESS = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def raw(
    tx_hash: str = "a" * 64,
    *,
    timestamp: datetime | None = datetime(2025, 1, 1, tzinfo=UTC),
    confirmed: bool = True,
    amount: str = "1",
) -> ProviderRawRecord:
    return ProviderRawRecord(
        chain=Chain.BITCOIN,
        source_provider="primary",
        source_type="bitcoin_output",
        tx_hash=tx_hash,
        timestamp=timestamp,
        from_address=ADDRESS,
        to_address=ADDRESS,
        asset_symbol="BTC",
        amount_raw=amount,
        decimals=8,
        transaction_type="utxo_transfer",
        metadata={"confirmed": confirmed, "output_index": 0},
        raw_reference=f"output:{tx_hash}:0",
    )


def settings() -> Settings:
    return Settings.model_validate(
        {
            "providers": {
                "ethereum": {"primary": "ethereum"},
                "tron": {"primary": "tron"},
                "bitcoin": {"primary": "primary", "fallback": ["fallback"]},
            }
        }
    )


class PartialProvider(BaseProvider):
    chain = Chain.BITCOIN
    capabilities = frozenset({ProviderCapability.ADDRESS_TRANSACTIONS})

    def __init__(self, name: str, result: ProviderResult) -> None:
        self.name = name
        self.result = result
        self.calls = 0

    async def health_check(self) -> HealthCheck:
        return HealthCheck(self.name, self.chain, True)

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_primary_partial_missing_data_triggers_fallback_and_dedup() -> None:
    error = ProviderAuthenticationError(
        provider="primary",
        chain=Chain.BITCOIN,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        safe_message="authentication failed",
        missing_data_category="address_transactions",
    )
    primary_result = ProviderResult(
        "primary",
        Chain.BITCOIN,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        (raw(),),
        Completeness.PARTIAL,
        errors=(error,),
        missing_data=("address_transactions",),
    )
    fallback_result = ProviderResult(
        "fallback",
        Chain.BITCOIN,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        (raw(),),
        Completeness.COMPLETE,
    )
    registry = ProviderRegistry()
    primary = PartialProvider("primary", primary_result)
    fallback = PartialProvider("fallback", fallback_result)
    registry.register(primary)
    registry.register(fallback)
    result = await ProviderCollector(
        ProviderSelectionPolicy(registry, settings())
    ).collect_address(Chain.BITCOIN, ADDRESS)
    assert fallback.calls == 1
    assert len(result.records) == 1
    assert error in result.errors


@pytest.mark.asyncio
async def test_sufficient_partial_does_not_trigger_fallback() -> None:
    primary_result = ProviderResult(
        "primary",
        Chain.BITCOIN,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        (raw(),),
        Completeness.PARTIAL,
        warnings=("truncated",),
    )
    fallback_result = ProviderResult(
        "fallback",
        Chain.BITCOIN,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        (raw(),),
        Completeness.COMPLETE,
    )
    registry = ProviderRegistry()
    registry.register(PartialProvider("primary", primary_result))
    fallback = PartialProvider("fallback", fallback_result)
    registry.register(fallback)
    await ProviderCollector(
        ProviderSelectionPolicy(registry, settings())
    ).collect_address(Chain.BITCOIN, ADDRESS)
    assert fallback.calls == 0


@pytest.mark.asyncio
async def test_hard_record_limit_truncates_oversized_page_without_extra_request() -> None:
    calls = 0

    async def fetch(cursor, size):
        nonlocal calls
        calls += 1
        return ProviderPage(tuple(raw(str(index) * 64) for index in range(5)), "next")

    result = await paginate(
        provider="mock",
        chain=Chain.BITCOIN,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=10, max_records=2, page_size=100),
    )
    assert calls == 1
    assert len(result.records) == 2
    assert result.truncated
    assert result.truncation_reason == "max_records"
    assert result.available_more


@pytest.mark.asyncio
async def test_exact_record_limit_without_cursor_is_complete() -> None:
    async def fetch(cursor, size):
        return ProviderPage((raw("a" * 64), raw("b" * 64)), None)

    result = await paginate(
        provider="mock",
        chain=Chain.BITCOIN,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=10, max_records=2, page_size=100),
    )
    assert not result.truncated
    assert not result.available_more
    assert result.completeness is Completeness.COMPLETE


def test_unconfirmed_bitcoin_accepts_null_timestamp_without_fabrication() -> None:
    transaction = DataPipeline().to_domain(
        ProviderRecordImporter().load((raw(timestamp=None, confirmed=False),))
    )[0]
    assert transaction.timestamp is None


def test_confirmed_bitcoin_still_requires_timestamp() -> None:
    with pytest.raises(PipelineValidationError):
        DataPipeline().to_domain(
            ProviderRecordImporter().load((raw(timestamp=None, confirmed=True),))
        )


def test_analysis_retains_unconfirmed_but_timeline_excludes_it() -> None:
    transactions = DataPipeline().to_domain(
        ProviderRecordImporter().load(
            (
                raw("a" * 64),
                raw("b" * 64, timestamp=None, confirmed=False),
            )
        )
    )
    result = AnalysisEngine().analyze(transactions, ADDRESS)
    assert result.summary.transaction_count == 2
    assert result.summary.unconfirmed_count == 1
    assert sum(bucket.transaction_count for bucket in result.timeline.daily.values()) == 1
    assert result.metadata["missing_timestamp_count"] == 1
    assert any("excluded_unconfirmed_without_timestamp" in item for item in result.warnings)


def test_provider_partial_pipeline_retains_valid_and_rejects_invalid() -> None:
    result = ProviderRecordImporter().to_domain_partial(
        (raw("a" * 64), raw("b" * 64, amount="nan")),
        DataPipeline(),
    )
    assert len(result.transactions) == 1
    assert len(result.rejected_records) == 1
    assert result.rejected_records[0].raw_reference == f"output:{'b' * 64}:0"
    assert result.rejected_records[0].reasons[0]["code"] == "invalid_amount"


def test_all_invalid_provider_records_produce_no_domain_transactions() -> None:
    result = ProviderRecordImporter().to_domain_partial(
        (raw(amount="nan"),), DataPipeline()
    )
    assert result.transactions == ()
    assert len(result.rejected_records) == 1
