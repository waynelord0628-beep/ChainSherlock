from datetime import UTC, datetime

import httpx
import pytest
import respx

from crypto_investigator.domain import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.dedup import deduplicate_records
from crypto_investigator.providers.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    UnsupportedCapabilityError,
)
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.models import (
    Completeness,
    HealthCheck,
    ProviderCapability,
    ProviderPage,
    ProviderRawRecord,
)
from crypto_investigator.providers.pagination import PaginationLimits, paginate
from crypto_investigator.providers.rate_limit import AsyncRateLimiter


class ExampleProvider(BaseProvider):
    chain = Chain.ETHEREUM
    name = "example"
    capabilities = frozenset({ProviderCapability.TRANSACTION})

    async def health_check(self):
        return HealthCheck(self.name, self.chain, True)


def record(source_type="normal_transaction", **metadata):
    return ProviderRawRecord(
        chain=Chain.ETHEREUM,
        source_provider="example",
        source_type=source_type,
        tx_hash="0xabc",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        metadata=metadata,
    )


def test_base_provider_supports_capability():
    provider = ExampleProvider()
    assert provider.supports(ProviderCapability.TRANSACTION)
    assert not provider.supports(ProviderCapability.BALANCE)


@pytest.mark.asyncio
async def test_unsupported_capability_is_explicit():
    with pytest.raises(UnsupportedCapabilityError):
        await ExampleProvider().get_balance("0xabc")


def test_error_safe_dict_contains_structured_fields():
    error = ProviderAuthenticationError(
        provider="example",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.BALANCE,
        safe_message="authentication failed",
        status_code=401,
    )
    assert error.to_safe_dict()["provider"] == "example"
    assert error.to_safe_dict()["status_code"] == 401


@pytest.mark.asyncio
@respx.mock
async def test_http_authentication_error():
    respx.get("https://provider.test/data").mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )
    client = ProviderHttpClient(
        provider="example",
        chain=Chain.ETHEREUM,
        retries=1,
        rate_limiter=AsyncRateLimiter(1000),
    )
    with pytest.raises(ProviderAuthenticationError):
        await client.request_json(
            "GET",
            "https://provider.test/data",
            capability=ProviderCapability.TRANSACTION,
        )
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_http_rate_limit_error_after_retry_exhaustion():
    route = respx.get("https://provider.test/data").mock(
        return_value=httpx.Response(429, json={"error": "rate"})
    )
    client = ProviderHttpClient(
        provider="example",
        chain=Chain.ETHEREUM,
        retries=2,
        rate_limiter=AsyncRateLimiter(1000),
    )
    with pytest.raises(ProviderRateLimitError):
        await client.request_json(
            "GET",
            "https://provider.test/data",
            capability=ProviderCapability.TRANSACTION,
        )
    assert route.call_count == 2
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_http_timeout_retry_exhaustion():
    route = respx.get("https://provider.test/data").mock(
        side_effect=httpx.ReadTimeout("timeout")
    )
    client = ProviderHttpClient(
        provider="example",
        chain=Chain.ETHEREUM,
        retries=2,
        rate_limiter=AsyncRateLimiter(1000),
    )
    with pytest.raises(ProviderTimeoutError):
        await client.request_json(
            "GET",
            "https://provider.test/data",
            capability=ProviderCapability.TRANSACTION,
        )
    assert route.call_count == 2
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_http_malformed_response():
    respx.get("https://provider.test/data").mock(
        return_value=httpx.Response(200, text="not-json")
    )
    client = ProviderHttpClient(
        provider="example",
        chain=Chain.ETHEREUM,
        retries=1,
        rate_limiter=AsyncRateLimiter(1000),
    )
    with pytest.raises(ProviderResponseError):
        await client.request_json(
            "GET",
            "https://provider.test/data",
            capability=ProviderCapability.TRANSACTION,
        )
    await client.close()


@pytest.mark.asyncio
async def test_pagination_success_and_stop_condition():
    async def fetch(cursor, size):
        if cursor is None:
            return ProviderPage((record(),), "next")
        return ProviderPage((record(tx_index=2),), None)

    result = await paginate(
        provider="example",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.TRANSACTION,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=5, max_records=10),
    )
    assert len(result.records) == 2
    assert result.pages_fetched == 2
    assert result.completeness is Completeness.COMPLETE


@pytest.mark.asyncio
async def test_pagination_repeated_cursor_detection():
    async def fetch(cursor, size):
        return ProviderPage((record(),), "repeat")

    result = await paginate(
        provider="example",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.TRANSACTION,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=5, max_records=10),
    )
    assert result.completeness is Completeness.PARTIAL
    assert "Repeated pagination cursor detected" in result.warnings


@pytest.mark.asyncio
async def test_pagination_maximum_page_limit():
    async def fetch(cursor, size):
        return ProviderPage((record(),), str((int(cursor or "0")) + 1))

    result = await paginate(
        provider="example",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.TRANSACTION,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=2, max_records=10),
    )
    assert result.pages_fetched == 2
    assert "Maximum page limit reached" in result.warnings


@pytest.mark.asyncio
async def test_pagination_maximum_record_limit():
    async def fetch(cursor, size):
        return ProviderPage((record(), record(tx_index=2)), "next")

    result = await paginate(
        provider="example",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.TRANSACTION,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=5, max_records=1),
    )
    assert len(result.records) == 1
    assert "Maximum record limit reached" in result.warnings


def test_normal_transaction_deduplication():
    assert len(deduplicate_records((record(), record()))) == 1


def test_token_transfer_deduplication_preserves_log_indexes():
    records = (
        record("token_transfer", log_index=1),
        record("token_transfer", log_index=2),
    )
    assert len(deduplicate_records(records)) == 2


def test_internal_transfer_deduplication_preserves_trace_ids():
    records = (
        record("internal_transfer", trace_id="0"),
        record("internal_transfer", trace_id="1"),
    )
    assert len(deduplicate_records(records)) == 2


def test_bitcoin_io_deduplication_preserves_indexes():
    records = (
        record("bitcoin_output", output_index=0),
        record("bitcoin_output", output_index=1),
    )
    assert len(deduplicate_records(records)) == 2
