from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import asyncio

from crypto_investigator.domain.fifo_tracing import allocate_fifo
from crypto_investigator.domain.flow_patterns import detect_flow_patterns
from crypto_investigator.domain.fund_trace_engine import investigate_fund_trace
from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    FlowPatternType,
    SeedType,
    StopConditionType,
    TraceDirection,
    TraceEdge,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.reports.export import ReportExportCoordinator
from crypto_investigator.reports.multihop import compose_multihop_report
from crypto_investigator.providers.models import ProviderRawRecord
from crypto_investigator.providers.trace_adapter import records_to_trace_edges
from crypto_investigator.providers.multihop import collect_multihop_edges
from crypto_investigator.providers.collector import CollectionResult
from crypto_investigator.providers.models import (
    Completeness,
    PaginationMetadata,
    ProviderCapability,
    ProviderResult,
)
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.graphs.trace_adapter import trace_result_to_graph


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _edge(number, source, destination, amount, asset="USDT"):
    return TraceEdge(
        edge_id=f"EDGE-{number}",
        from_address=source,
        to_address=destination,
        transaction_hash=f"SYNTHETIC-TX-{number}",
        asset=asset,
        amount=Decimal(amount),
        timestamp=NOW + timedelta(minutes=number),
        allocation_method=AllocationMethod.DIRECT_TRANSACTION,
        confidence=Decimal("1"),
        evidence_refs=(f"SYNTHETIC-EVIDENCE-{number}",),
    )


def test_fifo_is_deterministic_and_never_crosses_assets():
    edges = (
        _edge(1, "SOURCE-A", "TARGET", "100"),
        _edge(2, "SOURCE-B", "TARGET", "50", "TRX"),
        _edge(3, "TARGET", "DEST-A", "40"),
        _edge(4, "TARGET", "DEST-B", "10", "TRX"),
        _edge(5, "TARGET", "DEST-C", "70"),
    )
    allocations, remaining = allocate_fifo(target_address="TARGET", edges=edges)
    assert [(item.asset, item.amount) for item in allocations] == [
        ("USDT", Decimal("40")),
        ("TRX", Decimal("10")),
        ("USDT", Decimal("60")),
    ]
    assert [(item.asset, item.remaining_amount) for item in remaining] == [
        ("TRX", Decimal("40")),
    ]
    assert allocate_fifo(target_address="TARGET", edges=edges) == (
        allocations,
        remaining,
    )


def test_patterns_remain_candidates_with_evidence():
    edges = (
        _edge(1, "SOURCE-A", "HUB", "10"),
        _edge(2, "SOURCE-B", "HUB", "10"),
        _edge(3, "SOURCE-C", "HUB", "10"),
        _edge(4, "HUB", "DEST-A", "10"),
        _edge(5, "HUB", "DEST-B", "10"),
        _edge(6, "HUB", "DEST-C", "10"),
        _edge(7, "DEST-A", "SEED", "5"),
    )
    findings = detect_flow_patterns(seed_address="SEED", nodes=(), edges=edges)
    assert {
        FlowPatternType.AGGREGATION,
        FlowPatternType.DISPERSION,
        FlowPatternType.RETURN_FLOW,
    }.issubset({item.pattern_type for item in findings})
    assert all(item.candidate_only and item.evidence_refs for item in findings)


@dataclass(frozen=True)
class _Label:
    address: str
    category: str = "exchange"
    label: str = "Synthetic Exchange"
    source: str = "synthetic-labels"
    verification_status: str = "trusted_local"


class _Labels:
    def check(self, chain, address):
        return (_Label(address),) if address == "VASP-ADDRESS" else ()


def test_five_hop_trace_stops_at_trusted_vasp_and_keeps_return_flow():
    edges = (
        _edge(1, "UPSTREAM", "SEED", "100"),
        _edge(2, "SEED", "HUB", "90"),
        _edge(3, "HUB", "BRANCH-A", "30"),
        _edge(4, "HUB", "BRANCH-B", "30"),
        _edge(5, "HUB", "BRANCH-C", "30"),
        _edge(6, "BRANCH-A", "VASP-ADDRESS", "25"),
        _edge(7, "VASP-ADDRESS", "BEYOND-VASP", "20"),
        _edge(8, "BRANCH-B", "SEED", "5"),
    )
    result, checkpoint = investigate_fund_trace(
        run_id="SYNTHETIC-RUN",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "synthetic-chain",
            "USDT",
            ("SYNTHETIC-SEED-EVIDENCE",),
        ),
        scope=TraceScope(
            "full_history",
            5,
            50,
            50,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.BIDIRECTIONAL,
        ),
        available_edges=edges,
        labels=_Labels(),
    )
    hashes = {edge.transaction_hash for edge in result.edges}
    assert result.status is TraceRunStatus.COMPLETED
    assert checkpoint is None
    assert "SYNTHETIC-TX-6" in hashes
    assert "SYNTHETIC-TX-7" not in hashes
    assert any(
        stop.condition is StopConditionType.CONFIRMED_EXCHANGE_OR_VASP
        for stop in result.stop_conditions
    )
    assert any(
        finding.pattern_type is FlowPatternType.RETURN_FLOW
        for finding in result.patterns
    )


def test_checkpoint_resume_does_not_skip_unfinished_frontier():
    edges = (
        _edge(1, "SEED", "HOP-1", "100"),
        _edge(2, "HOP-1", "HOP-2", "90"),
        _edge(3, "HOP-2", "HOP-3", "80"),
    )
    seed = TraceSeed(
        SeedType.ADDRESS,
        "SEED",
        "synthetic-chain",
        "USDT",
        ("SYNTHETIC-SEED-EVIDENCE",),
    )
    limited = TraceScope(
        "full_history",
        5,
        20,
        2,
        Decimal("1"),
        ("USDT",),
        direction=TraceDirection.FORWARD,
    )
    first, checkpoint = investigate_fund_trace(
        run_id="RESUME-RUN",
        seed=seed,
        scope=limited,
        available_edges=edges,
    )
    assert first.status is TraceRunStatus.PARTIAL
    assert checkpoint is not None

    expanded = TraceScope(
        "full_history",
        5,
        20,
        4,
        Decimal("1"),
        ("USDT",),
        direction=TraceDirection.FORWARD,
    )
    resumed, final_checkpoint = investigate_fund_trace(
        run_id="RESUME-RUN",
        seed=seed,
        scope=expanded,
        available_edges=edges,
        checkpoint=checkpoint,
        previous_result=first,
    )
    assert resumed.status is TraceRunStatus.COMPLETED
    assert final_checkpoint is None
    assert len(resumed.edges) == 3


def test_multihop_report_uses_bounded_tables_and_exports_offline(tmp_path):
    result, _ = investigate_fund_trace(
        run_id="SYNTHETIC-REPORT",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "synthetic-chain",
            "USDT",
            ("SYNTHETIC-SEED-EVIDENCE",),
        ),
        scope=TraceScope(
            "full_history",
            3,
            20,
            20,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.BIDIRECTIONAL,
        ),
        available_edges=(
            _edge(1, "SOURCE", "SEED", "100"),
            _edge(2, "SEED", "DESTINATION", "90"),
        ),
    )
    document = compose_multihop_report(result)
    assert document.metadata.report_type == "deterministic_multihop_trace"
    assert document.title == "多層資金追蹤與下車點候選分析報告"
    assert any(section.section_id == "hop_summary" for section in document.sections)
    assert any(section.section_id == "off_ramp_candidates" for section in document.sections)
    glossary = next(
        section for section in document.sections if section.section_id == "glossary"
    )
    glossary_text = " ".join(
        cell for table in glossary.tables for row in table.rows for cell in row
    )
    assert "Provider incomplete" in glossary_text
    assert "不代表該地址沒有後續活動" in glossary_text
    assert "FIFO（先進先出）" in glossary_text
    assert "Off-ramp（下車點）" in glossary_text
    assert "VASP（虛擬資產服務商）" in glossary_text
    assert "Graph truncation（圖譜截斷）" in glossary_text
    assert document.sections[-2].section_id == "glossary"
    assert document.sections[-1].section_id == "technical_appendix"
    assert "不代表已取得每個相關地址的無界完整歷史" in document.conclusion.text
    assert max(
        len(table.columns)
        for section in document.sections
        for table in section.tables
    ) <= 7

    exported = ReportExportCoordinator().export(document, tmp_path, "all")
    assert exported.status in {"complete", "partial"}
    for filename in ("report.md", "report.html", "report.docx", "report_data.json"):
        assert (tmp_path / filename).is_file()


def test_provider_adapter_keeps_trx_and_trc10_assets_separate():
    records = (
        ProviderRawRecord(
            chain=Chain.TRON,
            source_provider="synthetic-provider",
            source_type="normal_transaction",
            tx_hash="SYNTHETIC-TRX",
            timestamp=NOW,
            from_address="SOURCE",
            to_address="TARGET",
            asset_symbol="TRX",
            amount_raw="1000000",
            decimals=6,
            success=True,
            transaction_type="native_transfer",
            metadata={"contract_type": "TransferContract"},
        ),
        ProviderRawRecord(
            chain=Chain.TRON,
            source_provider="synthetic-provider",
            source_type="normal_transaction",
            tx_hash="SYNTHETIC-TRC10",
            timestamp=NOW,
            from_address="SOURCE",
            to_address="TARGET",
            asset_symbol="SYNTHETIC-ASSET",
            amount_raw="8888880000",
            decimals=6,
            success=True,
            transaction_type="token_transfer",
            metadata={"contract_type": "TransferAssetContract"},
        ),
    )
    conversion = records_to_trace_edges(records)
    assert conversion.rejected_count == 0
    assert [(edge.asset, edge.amount) for edge in conversion.edges] == [
        ("SYNTHETIC-ASSET", Decimal("8888.88")),
        ("TRX", Decimal("1")),
    ]


def test_provider_collection_is_budgeted_and_marks_partial():
    records_by_address = {
        "SEED": (
            ProviderRawRecord(
                Chain.TRON,
                "synthetic-provider",
                "token_transfer",
                "SYNTHETIC-TX-1",
                timestamp=NOW,
                from_address="SEED",
                to_address="HOP-1",
                asset_symbol="USDT",
                amount_raw="1000000",
                decimals=6,
                success=True,
            ),
        ),
        "HOP-1": (
            ProviderRawRecord(
                Chain.TRON,
                "synthetic-provider",
                "token_transfer",
                "SYNTHETIC-TX-2",
                timestamp=NOW + timedelta(minutes=1),
                from_address="HOP-1",
                to_address="HOP-2",
                asset_symbol="USDT",
                amount_raw="900000",
                decimals=6,
                success=True,
            ),
        ),
    }
    query_calls = []

    async def fetch(address, start_cursors, completed_capabilities):
        assert start_cursors == {}
        assert completed_capabilities == frozenset()
        query_calls.append(address)
        records = records_by_address.get(address, ())
        return CollectionResult(
            records,
            (
                ProviderResult(
                    "synthetic-provider",
                    Chain.TRON,
                    ProviderCapability.TOKEN_TRANSFERS,
                    records,
                    Completeness.COMPLETE,
                    pages_fetched=1,
                ),
            ),
            (),
        )

    result = asyncio.run(
        collect_multihop_edges(
            seed=TraceSeed(
                SeedType.ADDRESS,
                "SEED",
                "tron",
                "USDT",
                ("SYNTHETIC-EVIDENCE",),
            ),
            scope=TraceScope(
                "full_history",
                5,
                20,
                20,
                Decimal("0.1"),
                ("USDT",),
                direction=TraceDirection.FORWARD,
            ),
            fetch_address=fetch,
            max_address_queries=2,
        )
    )
    assert result.status is TraceRunStatus.PARTIAL
    assert result.address_query_count == 2
    assert query_calls.count("SEED") == 1
    assert {edge.transaction_hash for edge in result.edges} == {
        "SYNTHETIC-TX-1",
        "SYNTHETIC-TX-2",
    }


def test_depth_five_product_scenario_preserves_flow_patterns_and_vasp_stop():
    @dataclass(frozen=True)
    class Label:
        address: str
        label: str
        category: str
        source: str
        verification_status: str

    class Labels:
        def check(self, chain, address):
            if address == "VASP-ENDPOINT":
                return (
                    Label(
                        address,
                        "Synthetic VASP",
                        "vasp",
                        "synthetic-local-label",
                        "trusted_local",
                    ),
                )
            return ()

    edges = (
        _edge(101, "SOURCE-A", "SEED", "120"),
        _edge(102, "SOURCE-B", "SEED", "80"),
        _edge(103, "SEED", "HOP-1", "180"),
        _edge(104, "HOP-1", "HOP-2", "170"),
        _edge(105, "HOP-2", "BRANCH-A", "60"),
        _edge(106, "HOP-2", "BRANCH-B", "55"),
        _edge(107, "HOP-2", "BRANCH-C", "45"),
        _edge(108, "BRANCH-A", "SEED", "10"),
        _edge(109, "BRANCH-B", "VASP-ENDPOINT", "50"),
        _edge(110, "BRANCH-C", "REVENUE-SHARE", "20"),
    )
    result, checkpoint = investigate_fund_trace(
        run_id="SYNTHETIC-DEPTH-FIVE",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "tron",
            "USDT",
            ("SYNTHETIC-EVIDENCE",),
        ),
        scope=TraceScope(
            "synthetic_full_history",
            5,
            50,
            100,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.BIDIRECTIONAL,
        ),
        available_edges=edges,
        labels=Labels(),
    )
    assert checkpoint is None
    assert result.status is TraceRunStatus.COMPLETED
    assert {item.pattern_type for item in result.patterns} >= {
        FlowPatternType.AGGREGATION,
        FlowPatternType.DISPERSION,
        FlowPatternType.RETURN_FLOW,
    }
    assert result.off_ramp_candidates[0].address == "VASP-ENDPOINT"
    assert result.off_ramp_candidates[0].label == "Synthetic VASP"
    assert any(
        item.condition is StopConditionType.CONFIRMED_EXCHANGE_OR_VASP
        and item.reached
        for item in result.stop_conditions
    )
    assert all(
        item.transaction_hash.startswith("SYNTHETIC-TX-")
        for item in result.edges
    )


def test_manual_stop_is_reached_and_prevents_further_traversal():
    edges = (
        _edge(201, "SEED", "MANUAL-STOP", "100"),
        _edge(202, "MANUAL-STOP", "SHOULD-NOT-BE-VISITED", "90"),
    )
    result, checkpoint = investigate_fund_trace(
        run_id="SYNTHETIC-MANUAL-STOP",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "tron",
            "USDT",
            ("SYNTHETIC-EVIDENCE",),
        ),
        scope=TraceScope(
            "synthetic",
            5,
            20,
            20,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.FORWARD,
        ),
        available_edges=edges,
        manual_stop_addresses=("MANUAL-STOP",),
    )
    assert checkpoint is None
    assert any(
        item.condition is StopConditionType.MANUAL_STOP and item.reached
        for item in result.stop_conditions
    )
    assert "SHOULD-NOT-BE-VISITED" not in {
        item.address for item in result.nodes
    }


def test_per_node_branch_cap_keeps_largest_edges_and_records_limitation():
    edges = tuple(
        _edge(300 + index, "SEED", f"HOP-{index}", str(index))
        for index in range(1, 8)
    )
    result, checkpoint = investigate_fund_trace(
        run_id="SYNTHETIC-BRANCH-CAP",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "tron",
            "USDT",
            ("SYNTHETIC-EVIDENCE",),
        ),
        scope=TraceScope(
            "synthetic",
            1,
            20,
            20,
            Decimal("0"),
            ("USDT",),
            direction=TraceDirection.FORWARD,
            max_edges_per_node=3,
        ),
        available_edges=edges,
    )
    assert checkpoint is None
    assert [item.amount for item in result.edges] == [
        Decimal("7"),
        Decimal("6"),
        Decimal("5"),
    ]
    assert any(
        "Per-node edge cap 3 reached" in item.reason
        for item in result.stop_conditions
    )


def test_unlabeled_terminal_is_low_confidence_candidate_not_confirmed_off_ramp():
    result, _ = investigate_fund_trace(
        run_id="SYNTHETIC-UNLABELED-ENDPOINT",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "tron",
            "USDT",
            ("SYNTHETIC-EVIDENCE",),
        ),
        scope=TraceScope(
            "synthetic",
            2,
            20,
            20,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.FORWARD,
        ),
        available_edges=(_edge(401, "SEED", "UNLABELED-ENDPOINT", "500"),),
    )
    candidate = next(
        item
        for item in result.off_ramp_candidates
        if item.address == "UNLABELED-ENDPOINT"
    )
    assert candidate.category == "unlabeled_terminal_candidate"
    assert candidate.confidence == Decimal("0.30")
    assert candidate.label is None
    assert "unconfirmed" in " ".join(candidate.limitations).lower()
    assert all(
        item.condition is not StopConditionType.CONFIRMED_EXCHANGE_OR_VASP
        for item in result.stop_conditions
    )


def test_provider_collection_checkpoint_resumes_cursor_without_refetching():
    calls = []

    async def first_fetch(address, start_cursors, completed_capabilities):
        calls.append((address, dict(start_cursors), completed_capabilities))
        item = ProviderRawRecord(
            chain=Chain.TRON,
            source_provider="synthetic-provider",
            source_type="token_transfers",
            tx_hash="SYNTHETIC-CURSOR-TX-1",
            timestamp=NOW,
            from_address="SEED",
            to_address="HOP-1",
            asset_symbol="USDT",
            amount_raw="1000000",
            decimals=6,
            success=True,
        )
        return CollectionResult(
            (item,),
            (
                ProviderResult(
                    "synthetic-provider",
                    Chain.TRON,
                    ProviderCapability.TOKEN_TRANSFERS,
                    (item,),
                    Completeness.PARTIAL,
                    pages_fetched=1,
                    truncated=True,
                    available_more=True,
                    pagination=PaginationMetadata(
                        "synthetic-provider",
                        Chain.TRON,
                        ProviderCapability.TOKEN_TRANSFERS,
                        next_cursor="SYNTHETIC-CURSOR-2",
                        has_more=True,
                        pagination_complete=False,
                        completeness=Completeness.PARTIAL,
                    ),
                ),
            ),
            (),
        )

    scope = TraceScope(
        "full_history",
        1,
        10,
        10,
        Decimal("0.1"),
        ("USDT",),
        direction=TraceDirection.FORWARD,
    )
    seed = TraceSeed(
        SeedType.ADDRESS,
        "SEED",
        "tron",
        "USDT",
        ("SYNTHETIC-EVIDENCE",),
    )
    first = asyncio.run(
        collect_multihop_edges(
            seed=seed,
            scope=scope,
            fetch_address=first_fetch,
            max_address_queries=1,
        )
    )
    assert first.checkpoint is not None

    async def resumed_fetch(address, start_cursors, completed_capabilities):
        calls.append((address, dict(start_cursors), completed_capabilities))
        assert start_cursors == {
            ProviderCapability.TOKEN_TRANSFERS.value: "SYNTHETIC-CURSOR-2"
        }
        return CollectionResult(
            (),
            (
                ProviderResult(
                    "synthetic-provider",
                    Chain.TRON,
                    ProviderCapability.TOKEN_TRANSFERS,
                    (),
                    Completeness.COMPLETE,
                    pages_fetched=1,
                    pagination=PaginationMetadata(
                        "synthetic-provider",
                        Chain.TRON,
                        ProviderCapability.TOKEN_TRANSFERS,
                        pagination_complete=True,
                        completeness=Completeness.COMPLETE,
                    ),
                ),
            ),
            (),
        )

    resumed = asyncio.run(
        collect_multihop_edges(
            seed=seed,
            scope=scope,
            fetch_address=resumed_fetch,
            max_address_queries=1,
            checkpoint=first.checkpoint,
            previous_edges=first.edges,
        )
    )
    assert len(calls) == 2
    assert resumed.status is TraceRunStatus.COMPLETED
    assert resumed.checkpoint is None
    assert [edge.transaction_hash for edge in resumed.edges] == [
        "SYNTHETIC-CURSOR-TX-1"
    ]


def test_provider_collection_without_asset_filter_keeps_discovered_assets():
    records = (
        ProviderRawRecord(
            Chain.TRON,
            "synthetic-provider",
            "token_transfer",
            "SYNTHETIC-DISCOVERY-USDT",
            timestamp=NOW,
            from_address="SEED",
            to_address="USDT-HOP",
            asset_symbol="USDT",
            amount_raw="2000000",
            decimals=6,
            success=True,
        ),
        ProviderRawRecord(
            Chain.TRON,
            "synthetic-provider",
            "normal_transaction",
            "SYNTHETIC-DISCOVERY-TRX",
            timestamp=NOW,
            from_address="SEED",
            to_address="TRX-HOP",
            asset_symbol="TRX",
            amount_raw="3000000",
            decimals=6,
            success=True,
            transaction_type="native_transfer",
            metadata={"contract_type": "TransferContract"},
        ),
    )
    calls = []

    async def fetch(address, start_cursors, completed_capabilities):
        calls.append(address)
        return CollectionResult(
            records if address == "SEED" else (),
            (
                ProviderResult(
                    "synthetic-provider",
                    Chain.TRON,
                    ProviderCapability.TOKEN_TRANSFERS,
                    records if address == "SEED" else (),
                    Completeness.COMPLETE,
                    pages_fetched=1,
                ),
            ),
            (),
        )

    result = asyncio.run(
        collect_multihop_edges(
            seed=TraceSeed(
                SeedType.ADDRESS,
                "SEED",
                "tron",
                None,
                ("SYNTHETIC-EVIDENCE",),
            ),
            scope=TraceScope(
                "synthetic",
                1,
                10,
                20,
                Decimal("0"),
                (),
                direction=TraceDirection.FORWARD,
            ),
            fetch_address=fetch,
            max_address_queries=1,
        )
    )
    assert calls == ["SEED"]
    assert {item.asset for item in result.edges} == {"TRX", "USDT"}


def test_provider_frontier_cap_uses_largest_material_edges():
    seed_records = tuple(
        ProviderRawRecord(
            Chain.TRON,
            "synthetic-provider",
            "token_transfer",
            f"SYNTHETIC-PRIORITY-{index}",
            timestamp=NOW,
            from_address="SEED",
            to_address=f"HOP-{index}",
            asset_symbol="USDT",
            amount_raw=str(index * 1_000_000),
            decimals=6,
            success=True,
        )
        for index in range(1, 6)
    )
    calls = []

    async def fetch(address, start_cursors, completed_capabilities):
        calls.append(address)
        records = seed_records if address == "SEED" else ()
        return CollectionResult(
            records,
            (
                ProviderResult(
                    "synthetic-provider",
                    Chain.TRON,
                    ProviderCapability.TOKEN_TRANSFERS,
                    records,
                    Completeness.COMPLETE,
                    pages_fetched=1,
                ),
            ),
            (),
        )

    result = asyncio.run(
        collect_multihop_edges(
            seed=TraceSeed(
                SeedType.ADDRESS,
                "SEED",
                "tron",
                "USDT",
                ("SYNTHETIC-EVIDENCE",),
            ),
            scope=TraceScope(
                "synthetic",
                2,
                20,
                20,
                Decimal("0"),
                ("USDT",),
                direction=TraceDirection.FORWARD,
                max_edges_per_node=2,
            ),
            fetch_address=fetch,
            max_address_queries=3,
        )
    )
    assert calls == ["SEED", "HOP-4", "HOP-5"]
    assert result.status is TraceRunStatus.PARTIAL
    assert any("provider frontier cap 2" in item for item in result.limitations)


def test_trace_graph_preserves_assets_hops_and_off_ramp_category():
    result, _ = investigate_fund_trace(
        run_id="SYNTHETIC-GRAPH",
        seed=TraceSeed(
            SeedType.ADDRESS,
            "SEED",
            "tron",
            "USDT",
            ("SYNTHETIC-EVIDENCE",),
        ),
        scope=TraceScope(
            "full_history",
            3,
            20,
            20,
            Decimal("1"),
            ("USDT",),
            direction=TraceDirection.FORWARD,
        ),
        available_edges=(
            _edge(1, "SEED", "HOP-1", "100"),
            _edge(2, "HOP-1", "VASP-ADDRESS", "90"),
        ),
        labels=_Labels(),
    )
    graph = trace_result_to_graph(result)
    assert graph.metadata.truncated is False
    assert graph.metadata.included_edge_count == 2
    vasp = next(node for node in graph.nodes if node.address == "VASP-ADDRESS")
    assert vasp.category == "exchange"
    assert vasp.metadata["minimum_hop"] == 2
    assert all(edge.assets == ("USDT",) for edge in graph.edges)
