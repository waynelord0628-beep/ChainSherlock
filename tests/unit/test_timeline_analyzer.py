from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.timeline import TimelineAnalyzer
from crypto_investigator.domain import Chain, Transaction


def tx(tx_hash, timestamp, amount="1", asset="ETH"):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        timestamp=timestamp,
        asset_symbol=asset,
        amount=Decimal(amount),
    )


def result():
    transactions = (
        tx("a", datetime(2026, 1, 5, 1, tzinfo=UTC), "1"),
        tx("b", datetime(2026, 1, 5, 2, tzinfo=UTC), "2"),
        tx("c", datetime(2026, 2, 6, 1, tzinfo=UTC), "100", "USDT"),
    )
    return TimelineAnalyzer().analyze(AnalysisContext(transactions))


def test_timeline_daily_counts():
    timeline = result()
    assert timeline.daily["2026-01-05"].transaction_count == 2
    assert timeline.daily["2026-02-06"].transaction_count == 1


def test_timeline_daily_assets_remain_separate():
    timeline = result()
    assert timeline.daily["2026-01-05"].amounts_by_asset == {"ETH": Decimal("3")}
    assert timeline.daily["2026-02-06"].amounts_by_asset == {
        "USDT": Decimal("100")
    }


def test_timeline_monthly_counts():
    timeline = result()
    assert timeline.monthly["2026-01"].transaction_count == 2
    assert timeline.monthly["2026-02"].transaction_count == 1


def test_timeline_hourly_distribution():
    assert result().hourly_distribution == {1: 2, 2: 1}


def test_timeline_weekly_distribution():
    assert result().weekly_distribution == {"Monday": 2, "Friday": 1}


def test_timeline_skips_missing_timestamp():
    transaction = tx("a", None)
    timeline = TimelineAnalyzer().analyze(AnalysisContext((transaction,)))
    assert timeline.daily == {}
    assert timeline.monthly == {}


def test_timeline_handles_empty_transactions():
    timeline = TimelineAnalyzer().analyze(AnalysisContext(()))
    assert timeline.hourly_distribution == {}
    assert timeline.weekly_distribution == {}
