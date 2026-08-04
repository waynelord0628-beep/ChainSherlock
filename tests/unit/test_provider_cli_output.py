from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from crypto_investigator.cli import app
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.collector import CollectionResult
from crypto_investigator.providers.errors import ProviderTimeoutError
from crypto_investigator.providers.models import (
    Completeness,
    ProviderCapability,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.output import write_provider_outputs


def collection() -> CollectionResult:
    record = ProviderRawRecord(
        Chain.ETHEREUM,
        "etherscan",
        "normal_transaction",
        "0x" + "1" * 64,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        amount_raw="1",
    )
    result = ProviderResult(
        "etherscan",
        Chain.ETHEREUM,
        ProviderCapability.ADDRESS_TRANSACTIONS,
        (record,),
        Completeness.PARTIAL,
        warnings=("limited",),
        missing_data=("internal_transactions",),
    )
    error = ProviderTimeoutError(
        provider="etherscan",
        chain=Chain.ETHEREUM,
        capability=ProviderCapability.INTERNAL_TRANSACTIONS,
        safe_message="timed out",
        retryable=True,
    )
    return CollectionResult((record,), (result,), (error,))


def test_provider_output_writes_status_errors_and_raw(tmp_path: Path) -> None:
    paths = write_provider_outputs(tmp_path, collection())
    assert paths["provider_status"].exists()
    assert paths["provider_errors"].exists()
    assert (tmp_path / "raw" / "etherscan.json").exists()
    status = paths["provider_status"].read_text(encoding="utf-8")
    errors = paths["provider_errors"].read_text(encoding="utf-8")
    assert '"final_completeness": "partial"' in status
    assert '"error_type": "ProviderTimeoutError"' in errors
    assert '"fallback_attempted": false' in errors


def test_provider_output_contains_no_api_key(tmp_path: Path) -> None:
    write_provider_outputs(tmp_path, collection())
    combined = "".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json"))
    assert "api_key" not in combined.casefold()


def test_cli_analyze_address_help_lists_provider_controls() -> None:
    result = CliRunner().invoke(app, ["analyze-address", "--help"])
    assert result.exit_code == 0
    assert "--refresh" in result.stdout
    assert "--max-records" in result.stdout


def test_cli_analyze_tx_requires_chain() -> None:
    result = CliRunner().invoke(app, ["analyze-tx", "a" * 64])
    assert result.exit_code == 2
    assert "--chain" in result.output


def test_cli_providers_lists_capabilities() -> None:
    result = CliRunner().invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "etherscan" in result.stdout
    assert "capabilities=" in result.stdout
