from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.counterparty import CounterpartyAnalyzer
from crypto_investigator.domain import Chain, Direction, Transaction

TARGET = "0x1111111111111111111111111111111111111111"
ALICE = "0x2222222222222222222222222222222222222222"
BOB = "0x3333333333333333333333333333333333333333"


def tx(tx_hash, source, target, amount, asset, hour):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        timestamp=datetime(2026, 1, 1, hour, tzinfo=UTC),
        from_address=source,
        to_address=target,
        asset_symbol=asset,
        amount=Decimal(amount),
    )


def result():
    transactions = (
        tx("a", ALICE, TARGET, "1", "ETH", 0),
        tx("b", TARGET, ALICE, "2", "ETH", 1),
        tx("c", ALICE, TARGET, "100", "USDT", 2),
        tx("d", TARGET, BOB, "3", "ETH", 3),
    )
    return CounterpartyAnalyzer().analyze(AnalysisContext(transactions, TARGET))


def test_counterparty_aggregation_count():
    assert len(result()) == 2


def test_counterparty_incoming_and_outgoing_counts():
    alice = result()[0]
    assert alice.incoming_count == 2
    assert alice.outgoing_count == 1
    assert alice.interaction_count == 3


def test_counterparty_keeps_assets_separate():
    alice = result()[0]
    assert alice.incoming_amount_by_asset == {
        "ETH": Decimal("1"),
        "USDT": Decimal("100"),
    }
    assert alice.outgoing_amount_by_asset == {"ETH": Decimal("2")}


def test_counterparty_first_and_last_seen():
    alice = result()[0]
    assert alice.first_seen == datetime(2026, 1, 1, 0, tzinfo=UTC)
    assert alice.last_seen == datetime(2026, 1, 1, 2, tzinfo=UTC)


def test_counterparty_mixed_direction_is_unknown():
    assert result()[0].direction is Direction.UNKNOWN


def test_counterparty_one_way_direction():
    bob = result()[1]
    assert bob.address == BOB
    assert bob.direction is Direction.OUTGOING


def test_counterparties_sorted_by_interaction_count():
    assert [item.address for item in result()] == [ALICE, BOB]


def test_counterparty_requires_resolvable_direction():
    transaction = tx("a", ALICE, BOB, "1", "ETH", 0)
    assert CounterpartyAnalyzer().analyze(AnalysisContext((transaction,))) == ()
