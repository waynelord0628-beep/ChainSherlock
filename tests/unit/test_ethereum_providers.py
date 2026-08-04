import httpx
import pytest
import respx

from crypto_investigator.domain import Chain
from crypto_investigator.providers.errors import ProviderAuthenticationError, ProviderRateLimitError
from crypto_investigator.providers.ethereum.blockscout import BlockscoutProvider
from crypto_investigator.providers.ethereum.etherscan import EtherscanProvider
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.models import ProviderCapability
from crypto_investigator.providers.pagination import PaginationLimits
from crypto_investigator.providers.rate_limit import AsyncRateLimiter


def etherscan():
    return EtherscanProvider(
        "secret",
        client=ProviderHttpClient(
            provider="etherscan",
            chain=Chain.ETHEREUM,
            retries=1,
            rate_limiter=AsyncRateLimiter(1000),
        ),
        limits=PaginationLimits(max_pages=2, max_records=10, page_size=10),
    )


NORMAL = {
    "blockNumber": "1",
    "timeStamp": "1767225600",
    "hash": "0xabc",
    "from": "0x1111111111111111111111111111111111111111",
    "to": "0x2222222222222222222222222222222222222222",
    "value": "1000000000000000000",
    "isError": "0",
    "gasUsed": "21000",
    "gasPrice": "2",
    "methodId": "0x",
}


@pytest.mark.asyncio
@respx.mock
async def test_etherscan_normal_transaction_parsing():
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=httpx.Response(200, json={"status": "1", "message": "OK", "result": [NORMAL]})
    )
    result = await etherscan().get_address_transactions(NORMAL["from"])
    assert result.records[0].asset_symbol == "ETH"
    assert result.records[0].amount_raw == "1000000000000000000"
    assert result.records[0].metadata["fee"] == "42000"


@pytest.mark.asyncio
@respx.mock
async def test_etherscan_token_transfer_parsing():
    token = {
        **NORMAL,
        "contractAddress": "0x3333333333333333333333333333333333333333",
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "value": "1000000",
        "logIndex": "7",
    }
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=httpx.Response(200, json={"status": "1", "message": "OK", "result": [token]})
    )
    result = await etherscan().get_token_transfers(NORMAL["from"])
    assert result.records[0].source_type == "token_transfer"
    assert result.records[0].metadata["log_index"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_etherscan_internal_transaction_parsing():
    internal = {**NORMAL, "traceId": "0_1"}
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=httpx.Response(200, json={"status": "1", "message": "OK", "result": [internal]})
    )
    result = await etherscan().get_internal_transactions(NORMAL["from"])
    assert result.records[0].metadata["trace_id"] == "0_1"


@pytest.mark.asyncio
@respx.mock
async def test_etherscan_api_key_error_redacted():
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=httpx.Response(200, json={"status": "0", "message": "NOTOK", "result": "Invalid API Key: secret"})
    )
    with pytest.raises(ProviderAuthenticationError) as captured:
        await etherscan().get_balance(NORMAL["from"])
    assert "secret" not in str(captured.value)


@pytest.mark.asyncio
@respx.mock
async def test_etherscan_rate_limit_message():
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=httpx.Response(200, json={"status": "0", "message": "NOTOK", "result": "Max rate limit reached"})
    )
    with pytest.raises(ProviderRateLimitError):
        await etherscan().get_balance(NORMAL["from"])


@pytest.mark.asyncio
@respx.mock
async def test_blockscout_transaction_parsing():
    payload = {
        "items": [{
            "hash": "0xabc",
            "block_number": 1,
            "timestamp": "2026-01-01T00:00:00Z",
            "from": {"hash": NORMAL["from"]},
            "to": {"hash": NORMAL["to"]},
            "value": "1",
            "status": "ok",
            "fee": {"value": "2"},
        }],
        "next_page_params": None,
    }
    respx.get("https://block.test/api/v2/addresses/address/transactions").mock(
        return_value=httpx.Response(200, json=payload)
    )
    provider = BlockscoutProvider(
        "https://block.test",
        client=ProviderHttpClient(
            provider="blockscout",
            chain=Chain.ETHEREUM,
            retries=1,
            rate_limiter=AsyncRateLimiter(1000),
        ),
    )
    result = await provider.get_address_transactions("address")
    assert result.records[0].success is True
    assert provider.supports(ProviderCapability.ADDRESS_TRANSACTIONS)
