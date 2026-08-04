import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from crypto_investigator.cli import app
from crypto_investigator.core.pipeline import DataPipeline, PipelineValidationError
from crypto_investigator.domain import Chain

ETH_FROM = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
ETH_TO = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
HEADERS = "from,to,amount,asset,timestamp,hash"


def write_csv(path: Path, row: str) -> Path:
    path.write_text(f"{HEADERS}\n{row}\n", encoding="utf-8")
    return path


def test_pipeline_csv_to_domain_and_exports(tmp_path: Path):
    source = write_csv(
        tmp_path / "transactions.csv",
        f"{ETH_FROM},{ETH_TO},2.5,ETH,2026-01-01T00:00:00Z,0xabc",
    )
    result = DataPipeline().run(source, output_dir=tmp_path / "output")
    assert result.transactions[0].chain is Chain.ETHEREUM
    assert result.transactions[0].from_address == ETH_FROM.lower()
    assert result.exports.transactions_csv.exists()
    assert result.exports.summary_json.exists()


def test_pipeline_exports_required_csv_columns(tmp_path: Path):
    source = write_csv(
        tmp_path / "transactions.csv",
        f"{ETH_FROM},{ETH_TO},2.5,ETH,2026-01-01,0xabc",
    )
    result = DataPipeline().run(source, output_dir=tmp_path / "output")
    frame = pd.read_csv(result.exports.transactions_csv)
    assert {"chain", "tx_hash", "amount", "metadata"}.issubset(frame.columns)
    assert frame.loc[0, "amount"] == 2.5


def test_pipeline_summary_is_not_analysis(tmp_path: Path):
    source = write_csv(
        tmp_path / "transactions.csv",
        f"{ETH_FROM},{ETH_TO},2.5,ETH,2026-01-01,0xabc",
    )
    result = DataPipeline().run(source, output_dir=tmp_path / "output")
    summary = json.loads(result.exports.summary_json.read_text(encoding="utf-8"))
    assert summary["transaction_count"] == 1
    assert summary["chains"] == {"ethereum": 1}
    assert summary["assets"] == {"ETH": 1}
    assert "counterparties" not in summary


def test_pipeline_stops_before_export_when_validation_fails(tmp_path: Path):
    source = write_csv(
        tmp_path / "transactions.csv",
        f"{ETH_FROM},{ETH_TO},invalid,ETH,2026-01-01,0xabc",
    )
    output = tmp_path / "output"
    with pytest.raises(PipelineValidationError):
        DataPipeline().run(source, output_dir=output)
    assert not output.exists()


def test_cli_analyze_file(tmp_path: Path, monkeypatch):
    source = write_csv(
        tmp_path / "transactions.csv",
        f"{ETH_FROM},{ETH_TO},2.5,ETH,2026-01-01,0xabc",
    )
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["analyze-file", str(source)])
    assert result.exit_code == 0
    assert "Normalized transactions: 1" in result.stdout
    assert (tmp_path / "output" / "transactions" / "transactions_normalized.csv").exists()


def test_cli_column_overrides(tmp_path: Path, monkeypatch):
    source = tmp_path / "custom.csv"
    source.write_text(
        "src,dst,total,coin,when,identifier\n"
        f"{ETH_FROM},{ETH_TO},3,ETH,2026-01-01,0xdef\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "analyze-file",
            str(source),
            "--from-column",
            "src",
            "--to-column",
            "dst",
            "--amount-column",
            "total",
            "--asset-column",
            "coin",
            "--time-column",
            "when",
            "--tx-column",
            "identifier",
        ],
    )
    assert result.exit_code == 0


def test_cli_reports_mapping_candidates(tmp_path: Path):
    source = tmp_path / "ambiguous.csv"
    source.write_text(
        "from,sender,to,amount,timestamp,hash\n"
        f"{ETH_FROM},{ETH_FROM},{ETH_TO},1,2026-01-01,0xabc\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["analyze-file", str(source)])
    assert result.exit_code == 2
    assert "ambiguous candidates" in result.stderr
