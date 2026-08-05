from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_investigator.analysis_materiality import (
    DEFAULT_TRX_DUST_THRESHOLD,
    split_material_transactions,
)
from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.core.pipeline import DataPipeline
from crypto_investigator.domain.metadata import Metadata
from crypto_investigator.domain.transaction import (
    Chain,
    Transaction,
    TransactionType,
)
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.importers.csv_importer import CsvImporter
from crypto_investigator.investigation.feature_engine import (
    InvestigationFeatureEngine,
)
from crypto_investigator.investigation.tron_assets import (
    other_asset_transfers,
    write_tron_other_asset_artifacts,
    write_trx_dust_exclusions,
)
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.presentation import prepare_report_for_display


TARGET = "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"
SOURCE = "TQPtmCQeYzn1iUWv6sun2aoKRYiBrB4Aq4"
DESTINATION = "TJMUadmxstaJsnsK6my4vEDGCDiXMh3eWd"
HEADERS = (
    "Tx Hash,blockHeight,blockTime(UTC+8),blockTime(UTC),from,to,"
    "value,symbol,contractType,status\n"
)


def csv_row(
    tx_hash: str,
    value: str,
    symbol: str,
    contract_type: str,
    *,
    sender: str = SOURCE,
    receiver: str = TARGET,
) -> str:
    return (
        f"{tx_hash},1,2025/05/31 00:47:06,2025/05/30 16:47:06,"
        f"{sender},{receiver},{value},{symbol},{contract_type},SUCCESS\n"
    )


def transaction(
    tx_hash: str,
    amount: str,
    symbol: str,
    contract_type: str,
    *,
    sender: str = SOURCE,
    receiver: str = TARGET,
) -> Transaction:
    return Transaction(
        chain=Chain.TRON,
        tx_hash=tx_hash,
        from_address=sender,
        to_address=receiver,
        asset_symbol=symbol,
        amount=Decimal(amount),
        timestamp=datetime(2025, 5, 30, 16, 47, 6, tzinfo=UTC),
        success=True,
        transaction_type=(
            TransactionType.NATIVE_TRANSFER
            if contract_type == "TransferContract"
            else TransactionType.TOKEN_TRANSFER
        ),
        metadata=Metadata({"contract_type": contract_type}),
    )


def test_tron_csv_mapping_preserves_contract_type_status_and_utc_time(tmp_path):
    path = tmp_path / "tron.csv"
    path.write_text(
        HEADERS + csv_row("tx-1", "1", "TRX", "TransferContract"),
        encoding="utf-8",
    )
    batch = CsvImporter().load(path)
    assert batch.records[0]["contract_type"] == "TransferContract"
    assert batch.records[0]["success"] == "SUCCESS"
    assert batch.records[0]["timestamp"] == "2025/05/30 16:47:06"


def test_transfer_asset_contract_never_becomes_trx(tmp_path):
    path = tmp_path / "tron.csv"
    path.write_text(
        HEADERS + csv_row("tx-1", "8888.88", "HX28com", "TransferAssetContract"),
        encoding="utf-8",
    )
    result = DataPipeline().run(path, output_dir=tmp_path / "out")
    assert result.transactions[0].asset_symbol == "HX28com"
    assert result.transactions[0].transaction_type is TransactionType.TOKEN_TRANSFER


@pytest.mark.parametrize(
    ("symbol", "amount"),
    (
        ("HX28com", "8888.88"),
        ("Pay.bi", "8888.88"),
        ("1005168", "4444.444444"),
        ("1005185", "4444.444444"),
        ("1005138", "888"),
        ("HASH8NET", "888.8"),
    ),
)
def test_known_trc10_examples_do_not_enter_trx(symbol, amount):
    analysis = AnalysisEngine().analyze(
        (transaction(f"tx-{symbol}", amount, symbol, "TransferAssetContract"),),
        TARGET,
    )
    assert "TRX" not in analysis.statistics.incoming_amount
    assert not analysis.flow.edges


def test_unknown_trc10_asset_does_not_fallback_to_trx(tmp_path):
    path = tmp_path / "tron.csv"
    path.write_text(
        HEADERS + csv_row("tx-1", "1", "", "TransferAssetContract"),
        encoding="utf-8",
    )
    result = DataPipeline().run(path, output_dir=tmp_path / "out")
    assert result.transactions[0].asset_symbol == "unknown_tron_asset"


def test_native_trx_regression_totals_remain_gross_values():
    transactions = (
        transaction("in-1", "5243.205056", "TRX", "TransferContract"),
        transaction(
            "out-1",
            "4621.517723",
            "TRX",
            "TransferContract",
            sender=TARGET,
            receiver=DESTINATION,
        ),
    )
    analysis = AnalysisEngine().analyze(transactions, TARGET)
    assert analysis.summary.incoming_count == 1
    assert analysis.summary.outgoing_count == 1
    assert analysis.statistics.incoming_amount["TRX"] == Decimal("5243.205056")
    assert analysis.statistics.outgoing_amount["TRX"] == Decimal("4621.517723")


def test_all_transfer_asset_contract_rows_enter_other_asset_artifact(tmp_path):
    transactions = tuple(
        transaction(f"tx-{index}", "888.8", "HASH8NET", "TransferAssetContract")
        for index in range(3)
    )
    paths = write_tron_other_asset_artifacts(transactions, tmp_path)
    assert len(other_asset_transfers(transactions)) == 3
    assert paths["transfers"].read_text(encoding="utf-8-sig").count(
        "TransferAssetContract"
    ) == 3
    assert '"transaction_count": 3' in paths["summary"].read_text(
        encoding="utf-8"
    )


def test_trc10_addresses_do_not_enter_counterparty_ranking():
    spam = transaction(
        "spam",
        "8888.88",
        "Pay.bi",
        "TransferAssetContract",
        sender="TL492pHAGYppvE8QKNwai8GakhuWjB8uE7",
    )
    material = transaction("material", "100", "TRX", "TransferContract")
    analysis = AnalysisEngine().analyze((spam, material), TARGET)
    assert {item.address for item in analysis.counterparties} == {SOURCE}
    assert len(analysis.flow.edges) == 1


def test_micro_trx_is_gross_but_not_behavior_analysis():
    dust = transaction("dust", "0.00001", "TRX", "TransferContract")
    material = transaction("material", "10", "TRX", "TransferContract")
    analysis = AnalysisEngine().analyze((dust, material), TARGET)
    assert analysis.summary.transaction_count == 2
    assert analysis.statistics.incoming_amount["TRX"] == Decimal("10.00001")
    assert len(analysis.flow.edges) == 1
    assert analysis.metadata["micro_trx_excluded_count"] == 1


def test_micro_trx_does_not_enter_investigation_or_ai_input():
    dust = transaction("dust-hash", "0.00001", "TRX", "TransferContract")
    material = transaction("material-hash", "10", "TRX", "TransferContract")
    analysis = AnalysisEngine().analyze((dust, material), TARGET)
    investigation = InvestigationFeatureEngine().analyze(analysis, TARGET)
    narrative_input = NarrativeInputBuilder().build(investigation)
    assert "dust-hash" not in str(investigation)
    assert "dust-hash" not in str(narrative_input)
    assert investigation.structured_metadata.source_transaction_count == 1


def test_micro_trx_dust_exclusion_is_reversible_and_exported(tmp_path):
    dust = transaction("dust", "0.00001", "TRX", "TransferContract")
    material, exclusions = split_material_transactions((dust,))
    assert not material
    assert exclusions[0].reversible is True
    path = write_trx_dust_exclusions((dust,), tmp_path)
    text = path.read_text(encoding="utf-8-sig")
    assert str(DEFAULT_TRX_DUST_THRESHOLD) in text
    assert "native_trx_below_materiality_threshold" in text


def test_report_separates_trc10_and_omits_old_quarantine_totals():
    dust_source = "TDustOnlyAddress111111111111111111111"
    transactions = (
        transaction("native", "10", "TRX", "TransferContract"),
        transaction(
            "dust-hash",
            "0.00001",
            "TRX",
            "TransferContract",
            sender=dust_source,
        ),
        transaction("other", "8888.88", "HX28com", "TransferAssetContract"),
    )
    analysis = AnalysisEngine().analyze(transactions, TARGET)
    report = prepare_report_for_display(
        ReportComposer().compose(
            analysis,
            target_address=TARGET,
            chain="tron",
            timezone="Asia/Taipei",
        )
    )
    rendered = str(report.sections)
    assert "TRC10／其他資產轉入摘要" in rendered
    assert "另有低於重要性門檻之微額轉入" in rendered
    assert "32,887.08" not in rendered
    assert "TRX 可疑轉入候選" not in rendered
    assert rendered.count("另有低於重要性門檻之微額轉入") == 1
    assert "dust-hash" not in rendered
    assert dust_source not in rendered


def test_native_trx_metadata_excludes_trc10_and_keeps_dust_in_gross_count():
    transactions = (
        transaction("native", "10", "TRX", "TransferContract"),
        transaction("dust", "0.00001", "TRX", "TransferContract"),
        transaction("other", "8888.88", "HX28com", "TransferAssetContract"),
    )
    metadata = AnalysisEngine().analyze(transactions, TARGET).metadata
    assert metadata["native_trx_transaction_count"] == 2
    assert metadata["native_trx_incoming_count"] == 2
    assert metadata["analysis_transaction_count"] == 1
    assert metadata["trc10_other_asset_excluded_count"] == 1


def test_graph_uses_material_transaction_count_not_gross_count():
    analysis = AnalysisEngine().analyze(
        (
            transaction("native", "10", "TRX", "TransferContract"),
            transaction("dust", "0.00001", "TRX", "TransferContract"),
            transaction("other", "8888.88", "HX28com", "TransferAssetContract"),
        ),
        TARGET,
    )
    graph = GraphBuilder().build(
        analysis,
        chain=Chain.TRON,
        target_address=TARGET,
    )
    assert graph.metadata.source_transaction_count == 1
