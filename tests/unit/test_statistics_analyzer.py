from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.statistics import StatisticsAnalyzer
from crypto_investigator.domain import Chain, Transaction

TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def tx(tx_hash, amount, asset, day, incoming=True):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        timestamp=datetime(2026, 1, day, tzinfo=UTC),
        from_address=OTHER if incoming else TARGET,
        to_address=TARGET if incoming else OTHER,
        asset_symbol=asset,
        amount=Decimal(amount),
    )


def result():
    transactions = (
        tx("a", "1", "ETH", 1, True),
        tx("b", "3", "ETH", 1, False),
        tx("c", "5", "ETH", 2, True),
        tx("d", "100", "USDT", 2, True),
    )
    return StatisticsAnalyzer().analyze(AnalysisContext(transactions, TARGET))


def test_statistics_keeps_incoming_assets_separate():
    assert result().incoming_amount == {
        "ETH": Decimal("6"),
        "USDT": Decimal("100"),
    }


def test_statistics_outgoing_amount():
    assert result().outgoing_amount == {"ETH": Decimal("3")}


def test_statistics_asset_breakdown():
    breakdown = result().asset_breakdown["ETH"]
    assert breakdown.transaction_count == 3
    assert breakdown.total_amount == Decimal("9")


def test_statistics_average_and_median_by_asset():
    statistics = result()
    assert statistics.average_amount["ETH"] == Decimal("3")
    assert statistics.median_amount["ETH"] == Decimal("3")
    assert statistics.average_amount["USDT"] == Decimal("100")


def test_statistics_max_and_min_transaction_by_asset():
    statistics = result()
    assert statistics.max_transaction["ETH"].tx_hash == "c"
    assert statistics.min_transaction["ETH"].tx_hash == "a"
    assert statistics.max_transaction["USDT"].amount == Decimal("100")


def test_statistics_top_asset_uses_transaction_count():
    assert result().top_asset == "ETH"


def test_statistics_transaction_frequency():
    assert result().transaction_frequency == 2.0


def test_statistics_handles_empty_transactions():
    statistics = StatisticsAnalyzer().analyze(AnalysisContext(()))
    assert statistics.asset_breakdown == {}
    assert statistics.top_asset is None
    assert statistics.transaction_frequency == 0.0
