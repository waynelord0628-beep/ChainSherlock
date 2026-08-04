from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.domain.transaction import (
    Chain,
    Direction,
    Transaction,
    TransactionType,
)
from crypto_investigator.graphs.builder import GraphBuilder, node_identity
from crypto_investigator.graphs.errors import GraphBuildError, GraphFilterError
from crypto_investigator.graphs.factory import GraphFactory
from crypto_investigator.graphs.models import GraphFilterOptions


TARGET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40
THIRD = "0x" + "c" * 40
START = datetime(2025, 1, 1, tzinfo=UTC)


def transaction(
    tx_hash: str,
    source: str = TARGET,
    target: str = OTHER,
    asset: str = "ETH",
    amount: str = "1",
    day: int = 0,
) -> Transaction:
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=tx_hash,
        from_address=source,
        to_address=target,
        asset_symbol=asset,
        amount=Decimal(amount),
        timestamp=START + timedelta(days=day),
        transaction_type=TransactionType.NATIVE_TRANSFER,
    )


def graph(transactions=None, options=None, target=TARGET):
    transactions = tuple(transactions or ())
    analysis = AnalysisEngine().analyze(transactions, target)
    return GraphBuilder().build(
        analysis,
        chain=Chain.ETHEREUM,
        target_address=target,
        options=options,
    )


def test_node_identity_includes_chain_and_normalizes_ethereum() -> None:
    assert node_identity(Chain.ETHEREUM, "0xABC") == "ethereum:0xabc"


@pytest.mark.parametrize(
    ("chain", "address"),
    [(Chain.TRON, "TABC"), (Chain.BITCOIN, "bc1QExample")],
)
def test_non_ethereum_node_identity_preserves_address(chain, address) -> None:
    assert node_identity(chain, address).endswith(address)


def test_target_node_is_created_and_marked() -> None:
    result = graph((transaction("1"),))
    target = next(node for node in result.nodes if node.is_target)
    assert target.address == TARGET


def test_counterparty_node_is_created() -> None:
    assert any(node.address == OTHER for node in graph((transaction("1"),)).nodes)


def test_outgoing_edge_direction() -> None:
    assert graph((transaction("1"),)).edges[0].direction is Direction.OUTGOING


def test_incoming_edge_direction() -> None:
    result = graph((transaction("1", OTHER, TARGET),))
    assert result.edges[0].direction is Direction.INCOMING


def test_self_transfer_is_preserved() -> None:
    result = graph((transaction("1", TARGET, TARGET),))
    assert result.edges[0].source == result.edges[0].target


def test_same_asset_edges_are_aggregated() -> None:
    result = graph((transaction("1"), transaction("2", amount="2")))
    assert len(result.edges) == 1
    assert result.edges[0].transaction_count == 2
    assert result.edges[0].amounts_by_asset["ETH"] == Decimal("3")


def test_multi_asset_edges_remain_separate() -> None:
    result = graph((transaction("1"), transaction("2", asset="USDT")))
    assert len(result.edges) == 2
    assert {edge.assets for edge in result.edges} == {("ETH",), ("USDT",)}


def test_transaction_hashes_are_deduplicated() -> None:
    result = graph((transaction("same"), transaction("same")))
    assert result.edges[0].transaction_hashes == ("same",)


def test_first_and_last_seen_are_aggregated() -> None:
    result = graph((transaction("1", day=2), transaction("2", day=5)))
    assert result.edges[0].first_seen == START + timedelta(days=2)
    assert result.edges[0].last_seen == START + timedelta(days=5)


def test_empty_flow_creates_target_only_graph() -> None:
    result = graph(())
    assert len(result.nodes) == 1
    assert result.edges == ()
    assert result.warnings[0].code == "no_edges"


def test_graph_factory_supports_registered_types() -> None:
    assert isinstance(GraphFactory.create("address_flow"), GraphBuilder)
    assert isinstance(GraphFactory.create("transaction_flow"), GraphBuilder)


def test_graph_factory_rejects_unknown_type() -> None:
    with pytest.raises(GraphBuildError):
        GraphFactory.create("unknown")


def test_include_asset_filter() -> None:
    result = graph(
        (transaction("1"), transaction("2", asset="USDT")),
        GraphFilterOptions(include_assets=("USDT",)),
    )
    assert [edge.assets for edge in result.edges] == [("USDT",)]


def test_exclude_asset_filter() -> None:
    result = graph(
        (transaction("1"), transaction("2", asset="USDT")),
        GraphFilterOptions(exclude_assets=("ETH",)),
    )
    assert [edge.assets for edge in result.edges] == [("USDT",)]


def test_minimum_transaction_filter() -> None:
    result = graph(
        (transaction("1"),),
        GraphFilterOptions(minimum_transaction_count=2),
    )
    assert result.edges == ()


def test_incoming_only_filter() -> None:
    result = graph(
        (transaction("1"), transaction("2", OTHER, TARGET)),
        GraphFilterOptions(incoming_only=True),
    )
    assert all(edge.direction is Direction.INCOMING for edge in result.edges)


def test_outgoing_only_filter() -> None:
    result = graph(
        (transaction("1"), transaction("2", OTHER, TARGET)),
        GraphFilterOptions(outgoing_only=True),
    )
    assert all(edge.direction is Direction.OUTGOING for edge in result.edges)


def test_conflicting_direction_filter_is_rejected() -> None:
    with pytest.raises(GraphFilterError):
        graph(
            (transaction("1"),),
            GraphFilterOptions(incoming_only=True, outgoing_only=True),
        )


def test_date_range_filter() -> None:
    result = graph(
        (transaction("1", day=0), transaction("2", THIRD, TARGET, day=5)),
        GraphFilterOptions(date_from=START + timedelta(days=3)),
    )
    assert len(result.edges) == 1
    assert result.edges[0].first_seen == START + timedelta(days=5)


def test_maximum_edges_is_hard_and_deterministic() -> None:
    transactions = (
        transaction("1", TARGET, OTHER),
        transaction("2", TARGET, THIRD),
    )
    first = graph(transactions, GraphFilterOptions(maximum_edges=1))
    second = graph(reversed(transactions), GraphFilterOptions(maximum_edges=1))
    assert len(first.edges) == 1
    assert first.edges[0].edge_id == second.edges[0].edge_id


def test_target_node_is_never_truncated() -> None:
    result = graph(
        (transaction("1", TARGET, OTHER), transaction("2", TARGET, THIRD)),
        GraphFilterOptions(maximum_nodes=1),
    )
    assert len(result.nodes) == 1
    assert result.nodes[0].is_target


def test_truncation_metadata_counts_excluded_items() -> None:
    result = graph(
        (transaction("1", TARGET, OTHER), transaction("2", TARGET, THIRD)),
        GraphFilterOptions(maximum_nodes=2, maximum_edges=1),
    )
    assert result.metadata.truncated
    assert result.metadata.excluded_node_count >= 1
    assert result.metadata.excluded_edge_count >= 1


def test_transaction_hash_safety_limit() -> None:
    result = graph(
        tuple(transaction(str(index)) for index in range(5)),
        GraphFilterOptions(maximum_transaction_hashes_per_edge=2),
    )
    assert len(result.edges[0].transaction_hashes) == 2
    assert result.edges[0].metadata["transaction_hashes_truncated"]
