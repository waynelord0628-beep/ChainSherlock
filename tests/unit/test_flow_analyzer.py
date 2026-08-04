from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.flow import FlowAnalyzer
from crypto_investigator.domain import Chain, Direction, Transaction

TARGET = "0x1111111111111111111111111111111111111111"
ALICE = "0x2222222222222222222222222222222222222222"
BOB = "0x3333333333333333333333333333333333333333"


def tx(tx_hash, source, target, amount="1", asset="ETH"):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        from_address=source,
        to_address=target,
        asset_symbol=asset,
        amount=Decimal(amount),
    )


def result():
    return FlowAnalyzer().analyze(
        AnalysisContext(
            (
                tx("a", ALICE, TARGET),
                tx("b", TARGET, BOB, "100", "USDT"),
            ),
            TARGET,
        )
    )


def test_flow_builds_unique_nodes():
    assert [node.address for node in result().nodes] == [TARGET, ALICE, BOB]


def test_flow_builds_one_edge_per_transaction():
    assert len(result().edges) == 2


def test_flow_edge_preserves_source_and_target():
    edge = result().edges[0]
    assert edge.source == ALICE
    assert edge.target == TARGET


def test_flow_edge_has_direction():
    assert result().edges[0].direction is Direction.INCOMING
    assert result().edges[1].direction is Direction.OUTGOING


def test_flow_edge_keeps_asset_and_weight_separate():
    eth, usdt = result().edges
    assert (eth.asset, eth.weight) == ("ETH", Decimal("1"))
    assert (usdt.asset, usdt.weight) == ("USDT", Decimal("100"))


def test_flow_skips_transaction_without_complete_edge():
    incomplete = tx("a", ALICE, TARGET)
    incomplete = Transaction(
        chain=incomplete.chain,
        tx_hash=incomplete.tx_hash,
        from_address=ALICE,
        to_address=None,
        amount=incomplete.amount,
        asset_symbol=incomplete.asset_symbol,
    )
    flow = FlowAnalyzer().analyze(AnalysisContext((incomplete,), TARGET))
    assert flow.nodes == ()
    assert flow.edges == ()


def test_flow_contains_no_graph_object():
    flow = result()
    assert set(flow.__dataclass_fields__) == {"nodes", "edges"}
