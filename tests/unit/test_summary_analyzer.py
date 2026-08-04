from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.summary import SummaryAnalyzer
from crypto_investigator.domain import Chain, Direction, Transaction

TARGET = "0x1111111111111111111111111111111111111111"
OTHER_A = "0x2222222222222222222222222222222222222222"
OTHER_B = "0x3333333333333333333333333333333333333333"


def tx(tx_hash, timestamp, source, target, asset="ETH", direction=Direction.UNKNOWN):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        timestamp=timestamp,
        from_address=source,
        to_address=target,
        asset_symbol=asset,
        amount=Decimal("1"),
        direction=direction,
    )


def context():
    return AnalysisContext(
        (
            tx("a", datetime(2026, 1, 1, tzinfo=UTC), OTHER_A, TARGET),
            tx("b", datetime(2026, 1, 1, 1, tzinfo=UTC), TARGET, OTHER_B),
            tx("c", datetime(2026, 1, 2, tzinfo=UTC), OTHER_A, TARGET, "USDT"),
        ),
        TARGET.upper(),
    )


def test_summary_transaction_count():
    assert SummaryAnalyzer().analyze(context()).transaction_count == 3


def test_summary_first_and_last_seen():
    result = SummaryAnalyzer().analyze(context())
    assert result.first_seen == datetime(2026, 1, 1, tzinfo=UTC)
    assert result.last_seen == datetime(2026, 1, 2, tzinfo=UTC)


def test_summary_counts_target_relative_directions():
    result = SummaryAnalyzer().analyze(context())
    assert result.incoming_count == 2
    assert result.outgoing_count == 1


def test_summary_unique_counterparties():
    assert SummaryAnalyzer().analyze(context()).unique_counterparties == 2


def test_summary_active_days_and_average():
    result = SummaryAnalyzer().analyze(context())
    assert result.active_days == 2
    assert result.average_daily_transactions == 1.5


def test_summary_assets_and_top_asset():
    result = SummaryAnalyzer().analyze(context())
    assert result.assets == ("ETH", "USDT")
    assert result.top_asset == "ETH"


def test_summary_handles_empty_transactions():
    result = SummaryAnalyzer().analyze(AnalysisContext(()))
    assert result.transaction_count == 0
    assert result.first_seen is None
    assert result.top_asset is None
