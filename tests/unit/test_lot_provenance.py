from datetime import UTC, datetime, timedelta
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import AllocationMethod, TraceEdge
from crypto_investigator.domain.lot_provenance import trace_fifo_provenance


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def edge(number, source, destination, amount, minute):
    return TraceEdge(
        edge_id=f"EDGE-{number}",
        from_address=source,
        to_address=destination,
        transaction_hash=f"TX-{number}",
        asset="USDT",
        amount=Decimal(amount),
        timestamp=NOW + timedelta(minutes=minute),
        allocation_method=AllocationMethod.DIRECT_TRANSACTION,
        confidence=Decimal("1"),
        evidence_refs=(f"EVIDENCE-{number}",),
    )


def test_fifo_provenance_uses_time_and_does_not_reuse_seed_amount():
    edges = (
        edge(1, "EXTERNAL", "A", "80", 1),
        edge(2, "SEED", "A", "100", 2),
        edge(3, "A", "BEFORE", "50", 0),
        edge(4, "A", "DRAIN-EXTERNAL", "80", 3),
        edge(5, "A", "DEST-1", "60", 4),
        edge(6, "A", "DEST-2", "60", 5),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=2,
        complete_addresses=frozenset({"A"}),
    )
    assert [
        (item.outgoing_edge_id, item.amount) for item in result.slices
    ] == [
        ("EDGE-5", Decimal("60")),
        ("EDGE-6", Decimal("40")),
    ]
    assert sum((item.amount for item in result.slices), Decimal("0")) == Decimal(
        "100"
    )


def test_fifo_provenance_propagates_transaction_evidence_across_hops():
    edges = (
        edge(1, "SEED", "A", "100", 1),
        edge(2, "A", "B", "70", 2),
        edge(3, "A", "C", "30", 3),
        edge(4, "B", "VASP", "70", 4),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=4,
        complete_addresses=frozenset({"A", "B", "C"}),
        terminal_addresses=frozenset({"VASP"}),
    )
    assert any(
        item.path_edge_ids == ("EDGE-1", "EDGE-2", "EDGE-4")
        and item.amount == Decimal("70")
        for item in result.slices
    )
    assert any(item.reason == "confirmed_terminal" for item in result.stops)
    assert all(item.evidence_refs for item in result.slices)


def test_fifo_provenance_stops_incomplete_address_without_inventing_path():
    edges = (
        edge(1, "SEED", "A", "100", 1),
        edge(2, "A", "B", "100", 2),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=3,
        complete_addresses=frozenset(),
    )
    assert result.slices == ()
    assert result.stops[0].reason == "provider_incomplete"
    assert result.stops[0].amount == Decimal("100")


def test_fifo_provenance_rejects_non_finite_or_implausible_amounts():
    huge = edge(2, "A", "BAD", "1E+71", 2)
    edges = (
        edge(1, "SEED", "A", "100", 1),
        huge,
        edge(3, "A", "GOOD", "100", 3),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=2,
        complete_addresses=frozenset({"A"}),
    )
    assert result.rejected_edge_ids == ("EDGE-2",)
    assert [(item.next_address, item.amount) for item in result.slices] == [
        ("GOOD", Decimal("100"))
    ]


def test_fifo_provenance_detects_return_without_looping():
    edges = (
        edge(1, "SEED", "A", "100", 1),
        edge(2, "A", "SEED", "40", 2),
        edge(3, "A", "B", "60", 3),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=4,
        complete_addresses=frozenset({"A", "B"}),
    )
    assert any(item.reason == "return_or_cycle_detected" for item in result.stops)
    assert len(result.slices) == 2


def test_fifo_provenance_does_not_reuse_converged_outgoing_capacity():
    edges = (
        edge(1, "SEED", "A", "60", 1),
        edge(2, "SEED", "A", "40", 2),
        edge(3, "A", "B", "100", 3),
        edge(4, "B", "C", "100", 4),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=3,
        complete_addresses=frozenset({"A", "B"}),
    )
    at_b = [
        item for item in result.slices if item.outgoing_edge_id == "EDGE-4"
    ]
    assert sum((item.amount for item in at_b), Decimal("0")) == Decimal("100")
    assert sorted(item.amount for item in at_b) == [
        Decimal("40"),
        Decimal("60"),
    ]


def test_every_transaction_edge_respects_its_global_capacity():
    edges = (
        edge(1, "SEED", "A", "70", 1),
        edge(2, "SEED", "A", "30", 2),
        edge(3, "A", "B", "100", 3),
        edge(4, "B", "C", "55", 4),
        edge(5, "B", "D", "45", 5),
    )
    result = trace_fifo_provenance(
        seed_address="SEED",
        edges=edges,
        max_depth=3,
        complete_addresses=frozenset({"A", "B"}),
    )
    capacities = {item.edge_id: item.amount for item in edges}
    for edge_id in ("EDGE-3", "EDGE-4", "EDGE-5"):
        allocated = sum(
            (
                item.amount
                for item in result.slices
                if item.outgoing_edge_id == edge_id
            ),
            Decimal("0"),
        )
        assert allocated <= capacities[edge_id]
