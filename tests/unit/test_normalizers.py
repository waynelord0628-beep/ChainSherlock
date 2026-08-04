from datetime import UTC
from decimal import Decimal

import pytest

from crypto_investigator.domain import Chain, Direction, Metadata, TransactionType
from crypto_investigator.normalizers.bitcoin import BitcoinNormalizer
from crypto_investigator.normalizers.ethereum import EthereumNormalizer
from crypto_investigator.normalizers.factory import NormalizerFactory
from crypto_investigator.normalizers.tron import TronNormalizer

ETH_FROM = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
ETH_TO = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
TRON_FROM = "T" + "a" * 33
TRON_TO = "T" + "b" * 33
BITCOIN_FROM = "bc1q" + "a" * 38
BITCOIN_TO = "bc1q" + "b" * 38


def record(from_address=ETH_FROM, to_address=ETH_TO, **changes):
    value = {
        "tx_hash": "0xabc",
        "timestamp": "2026-01-01T08:00:00+08:00",
        "block_number": "123",
        "from_address": from_address,
        "to_address": to_address,
        "asset_symbol": "ETH",
        "asset_contract": ETH_TO,
        "amount": "1.25",
        "decimals": "18",
        "direction": "incoming",
        "transaction_type": "native_transfer",
    }
    value.update(changes)
    return value


def test_ethereum_normalizer_lowercases_addresses():
    transaction = EthereumNormalizer().normalize(record())
    assert transaction.from_address == ETH_FROM.lower()
    assert transaction.asset_contract == ETH_TO.lower()


def test_tron_normalizer_preserves_base58():
    transaction = TronNormalizer().normalize(
        record(TRON_FROM, TRON_TO, asset_symbol="TRX", asset_contract=None)
    )
    assert transaction.from_address == TRON_FROM


def test_bitcoin_normalizer_preserves_address_format():
    transaction = BitcoinNormalizer().normalize(
        record(BITCOIN_FROM, BITCOIN_TO, asset_symbol="BTC", asset_contract=None)
    )
    assert transaction.from_address == BITCOIN_FROM


def test_normalizer_builds_complete_domain_transaction():
    transaction = EthereumNormalizer().normalize(record())
    assert transaction.chain is Chain.ETHEREUM
    assert transaction.amount == Decimal("1.25")
    assert transaction.block_number == 123
    assert transaction.decimals == 18
    assert transaction.direction is Direction.INCOMING
    assert transaction.transaction_type is TransactionType.NATIVE_TRANSFER
    assert transaction.timestamp.tzinfo is UTC
    assert isinstance(transaction.metadata, Metadata)


@pytest.mark.parametrize(
    ("chain", "normalizer_type"),
    [
        (Chain.ETHEREUM, EthereumNormalizer),
        (Chain.TRON, TronNormalizer),
        (Chain.BITCOIN, BitcoinNormalizer),
    ],
)
def test_normalizer_factory_selects_chain(chain, normalizer_type):
    assert isinstance(NormalizerFactory.create(chain), normalizer_type)


@pytest.mark.parametrize(
    ("address", "chain"),
    [
        (ETH_FROM, Chain.ETHEREUM),
        (TRON_FROM, Chain.TRON),
        (BITCOIN_FROM, Chain.BITCOIN),
    ],
)
def test_factory_detects_chain_from_address(address, chain):
    assert NormalizerFactory.chain_for_record({"from_address": address}) is chain


def test_factory_uses_explicit_chain():
    assert NormalizerFactory.chain_for_record({"chain": "tron"}) is Chain.TRON


def test_factory_rejects_unknown_chain():
    with pytest.raises(ValueError, match="Unsupported chain"):
        NormalizerFactory.create("solana")
