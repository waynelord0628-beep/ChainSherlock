import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.analyzers.factory import AnalyzerFactory
from crypto_investigator.analyzers.models import AnalysisResult
from crypto_investigator.analyzers.summary import SummaryAnalyzer
from crypto_investigator.domain import Chain, Transaction

TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def transactions():
    return (
        Transaction(
            chain=Chain.ETHEREUM,
            tx_hash="a",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            from_address=OTHER,
            to_address=TARGET,
            asset_symbol="ETH",
            amount=Decimal("1"),
        ),
    )


def test_factory_lists_all_analyzers():
    assert AnalyzerFactory.names() == (
        "summary",
        "statistics",
        "counterparty",
        "timeline",
        "flow",
    )


def test_factory_creates_analyzer_without_conditionals():
    assert isinstance(AnalyzerFactory.create("summary"), SummaryAnalyzer)


def test_factory_rejects_unknown_analyzer():
    with pytest.raises(ValueError, match="Unknown analyzer"):
        AnalyzerFactory.create("risk")


def test_engine_returns_analysis_result():
    result = AnalysisEngine().analyze(transactions(), TARGET)
    assert isinstance(result, AnalysisResult)
    assert result.summary.transaction_count == 1
    assert len(result.counterparties) == 1


def test_engine_metadata_records_completed_analyzers():
    result = AnalysisEngine().analyze(transactions(), TARGET)
    assert result.metadata["analyzers"] == AnalysisEngine.analyzer_names


def test_engine_warns_when_target_and_direction_are_unknown():
    result = AnalysisEngine().analyze(transactions())
    assert len(result.warnings) == 1


def test_exporter_writes_all_required_files(tmp_path):
    result = AnalysisEngine().analyze(transactions(), TARGET)
    paths = AnalysisExporter().export_all(result, tmp_path)
    assert set(paths) == {
        "analysis",
        "summary",
        "counterparties",
        "timeline_json",
        "timeline_csv",
        "flow",
    }
    assert all(path.exists() for path in paths.values())


def test_analysis_json_contains_complete_result(tmp_path):
    result = AnalysisEngine().analyze(transactions(), TARGET)
    paths = AnalysisExporter().export_all(result, tmp_path)
    payload = json.loads(paths["analysis"].read_text(encoding="utf-8"))
    assert set(payload) == {
        "summary",
        "statistics",
        "counterparties",
        "timeline",
        "flow",
        "metadata",
        "warnings",
    }


def test_counterparty_csv_keeps_asset_maps_as_json(tmp_path):
    result = AnalysisEngine().analyze(transactions(), TARGET)
    path = AnalysisExporter().export_all(result, tmp_path)["counterparties"]
    text = path.read_text(encoding="utf-8")
    assert "incoming_amount_by_asset" in text
    assert "ETH" in text


def test_flow_json_contains_data_not_graph_markup(tmp_path):
    result = AnalysisEngine().analyze(transactions(), TARGET)
    path = AnalysisExporter().export_all(result, tmp_path)["flow"]
    text = path.read_text(encoding="utf-8")
    assert '"nodes"' in text
    assert '"edges"' in text
    assert "<html" not in text.casefold()
