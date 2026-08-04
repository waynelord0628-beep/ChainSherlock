from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.domain.transaction import Chain, Transaction
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.styling import FUNDING_COLOR, STAGE_COLORS, node_color
from crypto_investigator.investigation import (
    InvestigationFeatureEngine,
    InvestigationSettings,
)
from crypto_investigator.investigation.clustering import analyze_relationships
from crypto_investigator.investigation.exchange import detect_services, load_labels
from crypto_investigator.investigation.investigation_result import (
    BehaviorSummary,
    ConclusionFacts,
    ConcentrationMetrics,
    DistributionMetrics,
    DormantPeriod,
    FundingAnalysis,
    FundingPeriod,
    FundingSource,
    FundingTransition,
    InvestigationResult,
    LabelRecord,
    Observation,
    OperationStage,
    RelationshipResult,
    ServiceDetection,
    TransferPattern,
)
from crypto_investigator.investigation.statistics import entropy, gini, herfindahl, median, ratio
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.investigation.export import InvestigationExporter
from crypto_investigator.labels.registry import LabelRegistry


TARGET = "0x" + "a" * 40
SOURCE_A = "0x" + "b" * 40
SOURCE_B = "0x" + "c" * 40
DESTINATION = "0x" + "d" * 40


def transaction(index, source, destination, amount, when, asset="USDT"):
    return Transaction(
        chain=Chain.ETHEREUM,
        tx_hash=f"0x{index:064x}",
        from_address=source,
        to_address=destination,
        asset_symbol=asset,
        amount=Decimal(amount),
        timestamp=when,
    )


@pytest.fixture
def analysis():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    records = [
        transaction(1, SOURCE_A, TARGET, "100", start),
        transaction(2, SOURCE_A, TARGET, "100", start + timedelta(minutes=1)),
        transaction(3, SOURCE_A, TARGET, "100", start + timedelta(minutes=2)),
        transaction(4, TARGET, DESTINATION, "100", start + timedelta(hours=1)),
        transaction(5, TARGET, DESTINATION, "100", start + timedelta(hours=1, minutes=1)),
        transaction(6, TARGET, DESTINATION, "100", start + timedelta(hours=1, minutes=2)),
        transaction(7, SOURCE_B, TARGET, "25.50", datetime(2025, 4, 20, tzinfo=UTC)),
        transaction(8, SOURCE_B, TARGET, "30.50", datetime(2025, 4, 21, tzinfo=UTC)),
        transaction(9, SOURCE_B, TARGET, "40.50", datetime(2025, 4, 22, tzinfo=UTC)),
        transaction(10, SOURCE_B, TARGET, "50.50", datetime(2025, 4, 23, tzinfo=UTC)),
    ]
    return AnalysisEngine().analyze(tuple(records), TARGET)


@pytest.fixture
def result(analysis):
    return InvestigationFeatureEngine().analyze(analysis, TARGET)


@pytest.mark.parametrize(
    "model,expected",
    [
        (FundingSource, "address"),
        (FundingPeriod, "period"),
        (FundingTransition, "occurred_at"),
        (FundingAnalysis, "sources"),
        (OperationStage, "stage"),
        (DormantPeriod, "dormant_days"),
        (ConcentrationMetrics, "herfindahl_index"),
        (LabelRecord, "category"),
        (ServiceDetection, "matched_rules"),
        (DistributionMetrics, "average_holding_seconds"),
        (TransferPattern, "batch_outgoing_count"),
        (RelationshipResult, "common_counterparties"),
        (BehaviorSummary, "funding_pattern"),
        (Observation, "facts"),
        (ConclusionFacts, "funding_source_changed"),
        (InvestigationResult, "conclusion_facts"),
        (InvestigationSettings, "dormant_days"),
    ],
)
def test_investigation_model_contracts(model, expected):
    assert expected in {field.name for field in fields(model)}


@pytest.mark.parametrize(
    "numerator,denominator,expected",
    [
        (0, 0, Decimal("0")),
        (1, 0, Decimal("0")),
        (0, 10, Decimal("0")),
        (1, 2, Decimal("0.5")),
        (2, 4, Decimal("0.5")),
        (3, 4, Decimal("0.75")),
        (10, 10, Decimal("1")),
    ],
)
def test_ratio_is_deterministic(numerator, denominator, expected):
    assert ratio(numerator, denominator) == expected


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], None),
        ([1], Decimal("1")),
        ([1, 3], Decimal("2")),
        ([3, 1, 2], Decimal("2")),
        ([Decimal("1.1"), Decimal("1.3")], Decimal("1.2")),
    ],
)
def test_median(values, expected):
    assert median(values) == expected


@pytest.mark.parametrize(
    "metric,values,expected",
    [
        (herfindahl, [], Decimal("0")),
        (herfindahl, [1], Decimal("1")),
        (herfindahl, [1, 1], Decimal("0.50")),
        (gini, [], Decimal("0")),
        (gini, [1], Decimal("0")),
        (gini, [1, 1], Decimal("0")),
        (entropy, [], Decimal("0")),
        (entropy, [1], Decimal("0.0")),
        (entropy, [1, 1], Decimal("1.0")),
    ],
)
def test_concentration_statistics(metric, values, expected):
    assert metric(values) == expected


@pytest.mark.parametrize(
    "attribute",
    ["sources", "periods", "transitions", "concentration"],
)
def test_funding_analysis_fields(result, attribute):
    assert getattr(result.funding, attribute) is not None


def test_funding_ranking_is_stable(result):
    assert [item.address for item in result.funding.sources] == [SOURCE_B, SOURCE_A]


@pytest.mark.parametrize(
    "address,count,ratio_value",
    [(SOURCE_B, 4, Decimal(4) / 7), (SOURCE_A, 3, Decimal(3) / 7)],
)
def test_funding_source_counts_and_ratios(result, address, count, ratio_value):
    item = next(source for source in result.funding.sources if source.address == address)
    assert item.transaction_count == count
    assert item.transaction_ratio == ratio_value


@pytest.mark.parametrize("period", ["2025-01", "2025-04"])
def test_funding_periods_are_month_scoped(result, period):
    assert period in {item.period for item in result.funding.periods}


def test_funding_transition_detected(result):
    assert result.funding.transitions[0].previous_source == SOURCE_A
    assert result.funding.transitions[0].current_source == SOURCE_B


@pytest.mark.parametrize("stage", ["startup", "dominant", "dormant", "recovery"])
def test_operation_stage_detection(result, stage):
    assert stage in {item.stage for item in result.stages}


@pytest.mark.parametrize(
    "attribute",
    [
        "started_at", "ended_at", "dormant_days", "reactivated",
        "post_recovery_average_amount_by_asset",
        "post_recovery_daily_frequency", "behavior_changed",
    ],
)
def test_dormant_period_contract(result, attribute):
    assert getattr(result.dormant_periods[0], attribute) is not None


def test_dormant_days_are_calendar_deterministic(result):
    assert result.dormant_periods[0].dormant_days == 108


@pytest.mark.parametrize(
    "attribute",
    ["top10_ratio", "top20_ratio", "top50_ratio", "herfindahl_index", "gini", "entropy"],
)
def test_counterparty_concentration_fields(result, attribute):
    assert isinstance(getattr(result.counterparty_concentration, attribute), Decimal)


@pytest.mark.parametrize("limit", ["top10_ratio", "top20_ratio", "top50_ratio"])
def test_counterparty_ratios_are_bounded(result, limit):
    assert Decimal("0") <= getattr(result.counterparty_concentration, limit) <= Decimal("1")


def test_csv_labels_are_loaded(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text("address,label,category\nabc,Known Exchange,exchange\n", encoding="utf-8")
    assert load_labels(path) == (LabelRecord("abc", "Known Exchange", "exchange", "csv"),)


@pytest.mark.parametrize("category", ["exchange", "otc", "payment", "service"])
def test_local_label_service_detection(analysis, category):
    address = analysis.counterparties[0].address
    found = detect_services(
        analysis.counterparties,
        (LabelRecord(address, "Known", category),),
    )
    assert found[0].service_type == category
    assert found[0].matched_rules == ("local_label",)


@pytest.mark.parametrize(
    "attribute",
    ["matched_transfer_count", "average_holding_seconds", "median_holding_seconds"],
)
def test_distribution_metrics(result, attribute):
    assert getattr(result.distribution, attribute) is not None


@pytest.mark.parametrize(
    "attribute",
    [
        "fixed_amounts", "integer_amount_ratio", "amount_suffix_counts",
        "batch_outgoing_count", "batch_incoming_count",
    ],
)
def test_transfer_pattern_fields(result, attribute):
    assert getattr(result.transfer_patterns, attribute) is not None


def test_fixed_amount_pattern_detected(result):
    assert Decimal("100") in result.transfer_patterns.fixed_amounts["USDT"]


def test_batch_distribution_detected(result):
    assert result.transfer_patterns.batch_outgoing_count == 1


def test_integer_amount_ratio_is_exact(result):
    assert result.transfer_patterns.integer_amount_ratio == Decimal("0.6")


@pytest.mark.parametrize(
    "attribute",
    [
        "funding_pattern", "distribution_pattern", "frequency",
        "counterparty_pattern", "activity_pattern", "operation_stages",
        "dormant", "recovery",
    ],
)
def test_behavior_summary_fields(result, attribute):
    assert getattr(result.behavior, attribute) is not None


@pytest.mark.parametrize(
    "attribute",
    [
        "funding_source_changed", "dormant_days", "main_counterparty_ratio",
        "top_provider_changed", "batch_distribution", "funding_concentration",
        "reactivated",
    ],
)
def test_conclusion_fact_fields(result, attribute):
    assert getattr(result.conclusion_facts, attribute) is not None


@pytest.mark.parametrize(
    "code",
    ["funding_source_changed", "dormant_reactivation", "batch_distribution"],
)
def test_rule_observations(result, code):
    assert code in {item.code for item in result.observations}


def test_relationship_common_counterparty(analysis):
    second = replace(
        analysis,
        counterparties=analysis.counterparties,
    )
    relationships = analyze_relationships({TARGET: analysis, SOURCE_A: second})
    assert relationships.common_counterparties


@pytest.mark.parametrize(
    "attribute",
    ["common_counterparties", "common_sources", "common_destinations"],
)
def test_relationship_result_is_deterministic_mapping(result, attribute):
    assert getattr(result.relationships, attribute) == {}


def test_same_input_produces_same_result(analysis):
    engine = InvestigationFeatureEngine()
    assert engine.analyze(analysis, TARGET) == engine.analyze(analysis, TARGET)


@pytest.mark.parametrize("runs", range(5))
def test_repeatability_across_runs(analysis, runs):
    assert InvestigationFeatureEngine().analyze(analysis, TARGET) == InvestigationFeatureEngine().analyze(analysis, TARGET)


def test_metadata_declares_deterministic_engine(result):
    assert result.metadata["engine_version"] == "6.5"
    assert result.metadata["deterministic"] is True


def test_report_contains_investigation_section(analysis, result):
    report = ReportComposer().compose(analysis, investigation=result)
    assert "investigation" in {section.section_id for section in report.sections}


def test_report_omits_investigation_when_not_provided(analysis):
    report = ReportComposer().compose(analysis)
    assert "investigation" not in {section.section_id for section in report.sections}


@pytest.mark.parametrize("stage,color", sorted(STAGE_COLORS.items()))
def test_stage_colors(stage, color):
    assert node_color("unknown", stage=stage) == color


def test_funding_color():
    assert node_color("unknown", funding_source=True) == FUNDING_COLOR


def test_graph_annotation_adds_stage_and_funding(analysis, result):
    graph = GraphBuilder().build(analysis, chain=Chain.ETHEREUM, target_address=TARGET)
    annotated = InvestigationFeatureEngine.annotate_graph(graph, result)
    target = next(node for node in annotated.nodes if node.is_target)
    source = next(node for node in annotated.nodes if node.address == SOURCE_A)
    assert target.metadata["operation_stage"] == result.stages[-1].stage
    assert source.metadata["funding_source"] is True


def test_investigation_json_round_trip_preserves_types(result, tmp_path):
    exporter = InvestigationExporter()
    path = exporter.write(result, tmp_path / "investigation.json")
    assert exporter.read(path) == result


@pytest.mark.parametrize("name", [
    "investigation.json", "investigation_evidence.json", "observations.json",
    "conclusion_facts.json", "label_matches.json",
])
def test_investigation_export_set(result, tmp_path, name):
    InvestigationExporter().export_all(result, tmp_path)
    assert (tmp_path / name).is_file()


def test_funding_is_asset_separated(result):
    source = result.funding.sources[0]
    assert source.share_by_asset["USDT"] == source.amounts_by_asset["USDT"] / Decimal("447.00")


def test_initial_funding_is_deterministic(result):
    candidate = result.initial_funding[0]
    assert candidate.source == SOURCE_A
    assert candidate.transaction_hash.endswith("1")


def test_activity_uses_configured_timezone(result):
    assert result.activity.timezone == "Asia/Taipei"
    assert result.activity.excluded_missing_timestamp_count == 0


def test_fifo_distribution_is_explicit(result):
    assert result.distribution_analysis.policy == "fifo_approximation"
    assert result.distribution_analysis.supported is True


@pytest.mark.parametrize("attribute", [
    "top1_ratio", "top3_ratio", "top5_ratio",
    "normalized_herfindahl_index", "effective_counterparty_count",
])
def test_extended_concentration_contract(result, attribute):
    assert isinstance(getattr(result.counterparty_concentration, attribute), Decimal)


def test_label_registry_csv_and_matching(tmp_path):
    path = tmp_path / "labels.csv"
    path.write_text(
        f"chain,address,label,category\nethereum,{SOURCE_A.upper()},Known,exchange\n",
        encoding="utf-8",
    )
    registry = LabelRegistry.import_file(path)
    assert registry.check("ethereum", SOURCE_A)[0].label == "Known"


def test_label_registry_json_round_trip(tmp_path):
    source = tmp_path / "labels.csv"
    source.write_text(
        "chain,address,label,category\ntron,TAbc,Pay,payment\n", encoding="utf-8"
    )
    registry = LabelRegistry.import_file(source)
    output = registry.write(tmp_path / "labels.json")
    assert LabelRegistry.import_file(output).records == registry.records


def test_matched_labels_are_exposed(analysis):
    label = LabelRecord(SOURCE_A, "Known", "exchange", chain="ethereum")
    found = InvestigationFeatureEngine().analyze(analysis, TARGET, labels=(label,))
    assert found.label_matches[0].category == "exchange"


def test_direction_reconciliation_is_complete(result):
    assert result.direction_reconciliation.reconciled is True


def test_structured_conclusion_facts_avoid_prohibited_judgments(result):
    prohibited = {"money_laundering", "fraud", "criminal", "suspect"}
    assert not prohibited.intersection(
        item.fact_code for item in result.conclusion_fact_items
    )


def test_public_mapping_reconciles_records_missing_flow_endpoints(analysis):
    value = AnalysisExporter.to_primitive(analysis)
    value["summary"]["transaction_count"] = 12
    value["summary"]["incoming_count"] = 7
    value["summary"]["outgoing_count"] = 3
    found = InvestigationFeatureEngine().analyze_public_mapping(value, TARGET)
    reconciliation = found.direction_reconciliation
    assert reconciliation.transaction_count == 12
    assert reconciliation.unclassified_direction_count == 2
    assert reconciliation.reconciled is True


def test_partial_result_facts_and_observations_are_traceable(analysis):
    partial = replace(analysis, metadata={**analysis.metadata, "completeness": "partial"})
    found = InvestigationFeatureEngine().analyze(partial, TARGET)
    assert all(item.evidence_refs for item in found.conclusion_fact_items)
    assert all(item.confidence == "low" for item in found.observations)
    assert all(item.limitations for item in found.observations)
    assert "startup" not in {item.stage for item in found.stages}
    assert found.dormant_periods == ()


def test_dust_trx_is_not_fixed_amount_pattern():
    start = datetime(2025, 1, 1, tzinfo=UTC)
    records = tuple(
        transaction(index, SOURCE_A, TARGET, "0.000001", start + timedelta(seconds=index), "TRX")
        for index in range(1, 5)
    )
    found = InvestigationFeatureEngine().analyze(
        AnalysisEngine().analyze(records, TARGET), TARGET
    )
    assert found.transfer_patterns.fixed_amounts["TRX"] == ()


@pytest.mark.parametrize("section_id", [
    "direction_reconciliation", "funding_analysis", "outgoing_distribution",
    "operation_stages", "dormancy", "holding_time", "transfer_patterns",
    "investigation_observations", "investigation_facts",
])
def test_report_has_quality_validation_sections(analysis, result, section_id):
    report = ReportComposer().compose(analysis, investigation=result)
    assert section_id in {section.section_id for section in report.sections}


def test_counterparty_report_remains_horizontal(analysis, result):
    report = ReportComposer().compose(analysis, investigation=result)
    section = next(
        item for item in report.sections
        if item.section_id == "outgoing_distribution"
    )
    assert section.tables[0].columns[:4] == ("排名", "地址", "標籤", "候選角色")


def test_report_evidence_index_includes_investigation_refs(analysis, result):
    report = ReportComposer().compose(analysis, investigation=result)
    artifact = next(
        item
        for item in report.evidence
        if item.evidence_id == "INVESTIGATION_ARTIFACT"
    )
    assert "IF0" in artifact.metadata["record_ids"]


@pytest.mark.parametrize("fact_code", [
    "dominant_funder_exists",
    "dominant_funder_address",
    "dominant_funder_share_by_asset",
    "funding_source_changed",
    "funding_transition_count",
    "dormant_period_detected",
    "longest_dormant_days",
    "reactivation_detected",
    "batch_incoming_detected",
    "batch_outgoing_detected",
])
def test_conclusion_fact_recalculation_matches_features(result, fact_code):
    expected = {
        "dominant_funder_exists": bool(result.funding.sources),
        "dominant_funder_address": {
            asset: addresses[0]
            for asset, addresses in result.funding.top_sources_by_asset.items()
            if addresses
        },
        "dominant_funder_share_by_asset": result.funding.concentration_by_asset,
        "funding_source_changed": bool(result.funding.transitions),
        "funding_transition_count": len(result.funding.transitions),
        "dormant_period_detected": bool(result.dormant_periods),
        "longest_dormant_days": max(
            (item.dormant_days for item in result.dormant_periods), default=0
        ),
        "reactivation_detected": any(
            item.reactivated for item in result.dormant_periods
        ),
        "batch_incoming_detected": bool(
            result.transfer_patterns.batch_incoming_count
        ),
        "batch_outgoing_detected": bool(
            result.transfer_patterns.batch_outgoing_count
        ),
    }
    fact = next(
        item for item in result.conclusion_fact_items
        if item.fact_code == fact_code
    )
    assert fact.value == expected[fact_code]
    assert fact.evidence_refs
