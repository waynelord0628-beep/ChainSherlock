from pathlib import Path

from typer.testing import CliRunner

import crypto_investigator.cli as cli
from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.domain.transaction import Chain, Transaction


TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "transactions.csv"
    path.write_text(
        "from,to,amount,asset,timestamp,hash\n"
        f"{TARGET},{OTHER},1,ETH,2026-01-01T00:00:00Z,0xabc\n",
        encoding="utf-8",
    )
    return path


def test_graph_file_writes_all_outputs(tmp_path: Path, monkeypatch) -> None:
    source = source_file(tmp_path)
    output = tmp_path / "graph"
    result = CliRunner().invoke(
        cli.app,
        [
            "graph-file",
            str(source),
            "--target",
            TARGET,
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (output / "flow_graph.json").exists()
    assert (output / "flow.graphml").exists()
    assert (output / "flow.html").exists()


def test_graph_file_filter_options_are_accepted(tmp_path: Path) -> None:
    source = source_file(tmp_path)
    result = CliRunner().invoke(
        cli.app,
        [
            "graph-file",
            str(source),
            "--target",
            TARGET,
            "--include-asset",
            "ETH",
            "--max-nodes",
            "2",
            "--max-edges",
            "1",
            "--output",
            str(tmp_path / "filtered"),
        ],
    )
    assert result.exit_code == 0, result.output


def test_graph_address_uses_mocked_provider_public_output(
    tmp_path: Path, monkeypatch
) -> None:
    async def fake_provider_analysis(**kwargs):
        output = kwargs["output_dir"]
        transaction = Transaction(
            chain=Chain.ETHEREUM,
            tx_hash="0xabc",
            from_address=TARGET,
            to_address=OTHER,
            asset_symbol="ETH",
        )
        result = AnalysisEngine().analyze((transaction,), TARGET)
        exporter = AnalysisExporter()
        exporter.write_json(output / "analysis.json", result)
        exporter.write_json(output / "provider_errors.json", [])
        exporter.write_json(output / "provider_status.json", [])
        return {"analysis": output / "analysis.json"}

    monkeypatch.setattr(cli, "analyze_provider_identifier", fake_provider_analysis)
    output = tmp_path / "provider_graph"
    result = CliRunner().invoke(
        cli.app,
        ["graph-address", TARGET, "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert (output / "flow_graph.json").exists()
    assert (output / "flow.graphml").exists()
    assert (output / "flow.html").exists()


def test_existing_cli_commands_remain_registered() -> None:
    result = CliRunner().invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "analyze-file",
        "analyze-address",
        "analyze-tx",
        "providers",
        "clear-cache",
    ):
        assert command in result.output
