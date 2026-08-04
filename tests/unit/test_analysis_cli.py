from pathlib import Path

from typer.testing import CliRunner

from crypto_investigator.cli import app

TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "transactions.csv"
    path.write_text(
        "from,to,amount,asset,timestamp,hash\n"
        f"{OTHER},{TARGET},1,ETH,2026-01-01T00:00:00Z,0xabc\n",
        encoding="utf-8",
    )
    return path


def test_cli_analyze_summary(tmp_path: Path, monkeypatch):
    source = source_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["analyze-summary", str(source), "--address", TARGET]
    )
    assert result.exit_code == 0
    assert (tmp_path / "output" / "transactions" / "summary.json").exists()


def test_cli_analyze_counterparty(tmp_path: Path, monkeypatch):
    source = source_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["analyze-counterparty", str(source), "--address", TARGET]
    )
    assert result.exit_code == 0
    assert (tmp_path / "output" / "transactions" / "counterparties.csv").exists()


def test_cli_analyze_timeline(tmp_path: Path, monkeypatch):
    source = source_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["analyze-timeline", str(source)])
    assert result.exit_code == 0
    assert (tmp_path / "output" / "transactions" / "timeline.json").exists()
    assert (tmp_path / "output" / "transactions" / "timeline.csv").exists()


def test_cli_analyze_all(tmp_path: Path, monkeypatch):
    source = source_file(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["analyze-all", str(source), "--address", TARGET]
    )
    assert result.exit_code == 0
    output = tmp_path / "output" / "transactions"
    assert (output / "analysis.json").exists()
    assert (output / "flow.json").exists()
