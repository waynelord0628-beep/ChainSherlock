import httpx
import pytest
import respx

from crypto_investigator.domain import Chain
from crypto_investigator.providers.bitcoin.blockstream import BlockstreamProvider
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.rate_limit import AsyncRateLimiter
from crypto_investigator.providers.tron.trongrid import TronGridProvider
from crypto_investigator.utils.tron import tron_address_to_base58

TRON_FROM = "TJRabPrwbZy45sbavfcjinPJC18kjpRTv8"
TRON_TO = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
BTC = "bc1q" + "a" * 38


def client(name, chain):
    return ProviderHttpClient(
        provider=name,
        chain=chain,
        retries=1,
        rate_limiter=AsyncRateLimiter(1000),
    )


@pytest.mark.asyncio
@respx.mock
async def test_trongrid_trx_parsing_and_base58_preservation():
    item = {
        "txID": "abc",
        "block_timestamp": 1767225600000,
        "ret": [{"contractRet": "SUCCESS"}],
        "raw_data": {"contract": [{"type": "TransferContract", "parameter": {"value": {
            "owner_address": TRON_FROM, "to_address": TRON_TO, "amount": 1000000
        }}}]},
    }
    respx.get(f"https://api.trongrid.io/v1/accounts/{TRON_FROM}/transactions").mock(
        return_value=httpx.Response(200, json={"data": [item], "meta": {}})
    )
    provider = TronGridProvider(client=client("trongrid", Chain.TRON))
    result = await provider.get_address_transactions(TRON_FROM)
    assert result.records[0].from_address == TRON_FROM
    assert result.records[0].amount_raw == "1000000"


@pytest.mark.asyncio
@respx.mock
async def test_trongrid_trc20_parsing():
    item = {
        "transaction_id": "abc",
        "block_timestamp": 1767225600000,
        "from": TRON_FROM,
        "to": TRON_TO,
        "value": "1000000",
        "token_info": {"address": TRON_TO, "symbol": "USDT", "decimals": 6},
        "event_index": 2,
    }
    respx.get(f"https://api.trongrid.io/v1/accounts/{TRON_FROM}/transactions/trc20").mock(
        return_value=httpx.Response(200, json={"data": [item], "meta": {}})
    )
    provider = TronGridProvider(client=client("trongrid", Chain.TRON))
    result = await provider.get_token_transfers(TRON_FROM)
    assert result.records[0].asset_symbol == "USDT"
    assert result.records[0].metadata["log_index"] == 2


def test_tron_hex_to_base58_is_explicit():
    assert tron_address_to_base58("41" + "00" * 20).startswith("T")


def test_tron_base58_input_is_unchanged():
    assert tron_address_to_base58(TRON_FROM) == TRON_FROM


@pytest.mark.asyncio
@respx.mock
async def test_blockstream_transaction_preserves_inputs_outputs():
    payload = {
        "txid": "abc",
        "fee": 100,
        "vin": [{"prevout": {"scriptpubkey_address": BTC, "value": 2000}}],
        "vout": [{"scriptpubkey_address": BTC, "value": 1900}],
        "status": {"confirmed": True, "block_height": 1, "block_time": 1767225600},
    }
    respx.get("https://blockstream.info/api/tx/abc").mock(
        return_value=httpx.Response(200, json=payload)
    )
    provider = BlockstreamProvider(client=client("blockstream", Chain.BITCOIN))
    result = await provider.get_transaction("abc")
    assert result.records[0].metadata["inputs"] == payload["vin"]
    assert result.records[0].metadata["outputs"] == payload["vout"]


def test_blockstream_address_incoming_keeps_only_target_outputs():
    other = "bc1q" + "b" * 38
    payload = {
        "txid": "abc",
        "vin": [{"prevout": {"scriptpubkey_address": other, "value": 3000}}],
        "vout": [
            {"scriptpubkey_address": BTC, "value": 1000},
            {"scriptpubkey_address": other, "value": 1900},
        ],
        "status": {"confirmed": True, "block_time": 1767225600},
    }
    records = BlockstreamProvider()._parse_transaction(
        payload, target_address=BTC
    )
    assert len(records) == 1
    assert records[0].to_address == BTC
    assert records[0].from_address == other


def test_blockstream_address_outgoing_uses_target_as_source():
    other = "bc1q" + "b" * 38
    payload = {
        "txid": "abc",
        "vin": [
            {"prevout": {"scriptpubkey_address": other, "value": 500}},
            {"prevout": {"scriptpubkey_address": BTC, "value": 3000}},
        ],
        "vout": [
            {"scriptpubkey_address": other, "value": 2500},
            {"scriptpubkey_address": BTC, "value": 900},
        ],
        "status": {"confirmed": True, "block_time": 1767225600},
    }
    records = BlockstreamProvider()._parse_transaction(
        payload, target_address=BTC
    )
    assert len(records) == 2
    assert {record.from_address for record in records} == {BTC}


@pytest.mark.asyncio
@respx.mock
async def test_blockstream_utxo_parsing():
    payload = [{"txid": "abc", "vout": 1, "value": 500, "status": {"confirmed": True, "block_height": 2}}]
    respx.get(f"https://blockstream.info/api/address/{BTC}/utxo").mock(
        return_value=httpx.Response(200, json=payload)
    )
    provider = BlockstreamProvider(client=client("blockstream", Chain.BITCOIN))
    result = await provider.get_utxos(BTC)
    assert result.records[0].metadata["utxo"] is True
    assert result.records[0].metadata["output_index"] == 1
    assert result.pagination.pagination_complete is True


@pytest.mark.asyncio
@respx.mock
async def test_blockstream_balance_from_funded_and_spent():
    payload = {
        "chain_stats": {"funded_txo_sum": 1000, "spent_txo_sum": 400},
        "mempool_stats": {"funded_txo_sum": 100, "spent_txo_sum": 50},
    }
    respx.get(f"https://blockstream.info/api/address/{BTC}").mock(
        return_value=httpx.Response(200, json=payload)
    )
    provider = BlockstreamProvider(client=client("blockstream", Chain.BITCOIN))
    balance = await provider.get_balance(BTC)
    assert balance.amount_raw == "650"
