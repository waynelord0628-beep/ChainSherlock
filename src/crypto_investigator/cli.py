from pathlib import Path
import asyncio
import shutil

import typer

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.analyzers.factory import AnalyzerFactory
from crypto_investigator.config import load_config
from crypto_investigator.core.pipeline import DataPipeline, PipelineValidationError
from crypto_investigator.detection.identifier import detect_identifier
from crypto_investigator.exceptions import ConfigurationError, InvalidIdentifierError
from crypto_investigator.importers.mapping import ColumnMappingError
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.factory import ProviderFactory
from crypto_investigator.providers.service import analyze_provider_identifier

app = typer.Typer(help="ChainSherlock: local-first blockchain transaction investigation toolkit.")


@app.command()
def detect(value: str = typer.Argument(..., help="Address or transaction hash to identify.")) -> None:
    """Detect the chain and type of an identifier."""
    try:
        identifier = detect_identifier(value)
    except InvalidIdentifierError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(identifier.model_dump_json(indent=2))


@app.command()
def providers(
    config: Path = typer.Option(Path("config/default.yaml"), exists=True),
    health: bool = typer.Option(False, "--health"),
) -> None:
    """List registered providers, capabilities, and optional health."""
    try:
        settings = load_config(config)
    except ConfigurationError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    registry = ProviderFactory.create_registry(settings)
    descriptors = (
        asyncio.run(registry.health()) if health else registry.descriptors()
    )
    for descriptor in descriptors:
        capabilities = ",".join(item.value for item in descriptor.capabilities)
        status = (
            f" health={'available' if descriptor.health.available else 'unavailable'}"
            if descriptor.health
            else ""
        )
        typer.echo(
            f"{descriptor.chain.value}: {descriptor.name} "
            f"capabilities={capabilities} api_key={descriptor.requires_api_key}{status}"
        )


@app.command("clear-cache")
def clear_cache(cache_dir: Path = typer.Option(Path("data/cache"))) -> None:
    """Remove locally cached provider responses."""
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        typer.echo(f"Cache cleared: {cache_dir}")
    else:
        typer.echo("Cache is already empty.")


def _run_provider_cli(
    identifier: str,
    chain: Chain,
    kind: str,
    provider: str | None,
    output: Path,
    max_pages: int,
    max_records: int,
    cache_ttl: int,
    refresh: bool,
) -> None:
    settings = load_config()
    settings.pagination.max_pages = max_pages
    settings.pagination.max_records = max_records
    settings.cache.ttl_seconds = cache_ttl
    try:
        paths = asyncio.run(
            analyze_provider_identifier(
                identifier=identifier,
                chain=chain,
                kind=kind,
                settings=settings,
                output_dir=output,
                provider=provider,
                refresh=refresh,
                cache_ttl=cache_ttl,
            )
        )
    except (ValueError, KeyError) as error:
        typer.echo(f"Provider analysis error: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"Analysis: {paths['analysis']}")
    typer.echo(f"Provider status: {paths['provider_status']}")


@app.command("analyze-address")
def analyze_address(
    address: str = typer.Argument(...),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    cache_ttl: int = typer.Option(86400, "--cache-ttl", min=1),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    output: Path = typer.Option(Path("output/provider"), "--output"),
) -> None:
    """Collect an address through providers, V2 Pipeline, and V3 Analysis."""
    try:
        detected = detect_identifier(address)
    except InvalidIdentifierError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from error
    selected_chain = chain or Chain(detected.chain.value)
    _run_provider_cli(
        detected.value,
        selected_chain,
        "address",
        provider,
        output,
        max_pages,
        max_records,
        cache_ttl,
        refresh,
    )


@app.command("analyze-tx")
def analyze_tx(
    tx_hash: str = typer.Argument(...),
    chain: Chain = typer.Option(..., "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    cache_ttl: int = typer.Option(86400, "--cache-ttl", min=1),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    output: Path = typer.Option(Path("output/provider"), "--output"),
) -> None:
    """Collect one transaction through providers, V2 Pipeline, and V3 Analysis."""
    _run_provider_cli(
        tx_hash,
        chain,
        "transaction",
        provider,
        output,
        max_pages,
        max_records,
        cache_ttl,
        refresh,
    )


@app.command("analyze-file")
def analyze_file(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    from_column: str | None = typer.Option(None, "--from-column"),
    to_column: str | None = typer.Option(None, "--to-column"),
    amount_column: str | None = typer.Option(None, "--amount-column"),
    asset_column: str | None = typer.Option(None, "--asset-column"),
    time_column: str | None = typer.Option(None, "--time-column"),
    tx_column: str | None = typer.Option(None, "--tx-column"),
) -> None:
    """Normalize a CSV or Excel transaction file through the V2 Data Pipeline."""
    overrides = {
        canonical: source
        for canonical, source in {
            "from_address": from_column,
            "to_address": to_column,
            "amount": amount_column,
            "asset_symbol": asset_column,
            "timestamp": time_column,
            "tx_hash": tx_column,
        }.items()
        if source is not None
    }
    try:
        result = DataPipeline().run(file, overrides)
    except ColumnMappingError as error:
        typer.echo(f"Column mapping error: {error}", err=True)
        raise typer.Exit(code=2) from error
    except PipelineValidationError as error:
        typer.echo(f"Validation error: {error}", err=True)
        for issue in error.issues:
            typer.echo(
                f"row={issue.row} field={issue.field} code={issue.code}: {issue.message}",
                err=True,
            )
        raise typer.Exit(code=2) from error
    except ValueError as error:
        typer.echo(f"Pipeline error: {error}", err=True)
        raise typer.Exit(code=2) from error

    typer.echo(f"Normalized transactions: {len(result.transactions)}")
    typer.echo(f"CSV: {result.exports.transactions_csv}")
    typer.echo(f"Summary: {result.exports.summary_json}")


def _domain_transactions(file: Path):
    try:
        return DataPipeline().run(file).transactions
    except (ColumnMappingError, PipelineValidationError, ValueError) as error:
        typer.echo(f"Analysis input error: {error}", err=True)
        raise typer.Exit(code=2) from error


def _analysis_output_dir(file: Path) -> Path:
    return Path("output") / file.stem


@app.command("analyze-summary")
def analyze_summary(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    address: str | None = typer.Option(None, "--address"),
) -> None:
    """Run the Summary Analyzer on Domain Transactions."""
    transactions = _domain_transactions(file)
    summary = AnalyzerFactory.create("summary").analyze(
        AnalysisContext(transactions, address)
    )
    path = _analysis_output_dir(file) / "summary.json"
    AnalysisExporter().write_summary(path, summary)
    typer.echo(f"Summary: {path}")


@app.command("analyze-counterparty")
def analyze_counterparty(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    address: str | None = typer.Option(None, "--address"),
) -> None:
    """Run the Counterparty Analyzer on Domain Transactions."""
    transactions = _domain_transactions(file)
    counterparties = AnalyzerFactory.create("counterparty").analyze(
        AnalysisContext(transactions, address)
    )
    path = _analysis_output_dir(file) / "counterparties.csv"
    AnalysisExporter().write_counterparties(path, counterparties)
    typer.echo(f"Counterparties: {path}")


@app.command("analyze-timeline")
def analyze_timeline(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Run the Timeline Analyzer on Domain Transactions."""
    transactions = _domain_transactions(file)
    timeline = AnalyzerFactory.create("timeline").analyze(
        AnalysisContext(transactions)
    )
    output_dir = _analysis_output_dir(file)
    exporter = AnalysisExporter()
    exporter.write_timeline_json(output_dir / "timeline.json", timeline)
    exporter.write_timeline_csv(output_dir / "timeline.csv", timeline)
    typer.echo(f"Timeline: {output_dir / 'timeline.json'}")


@app.command("analyze-all")
def analyze_all(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    address: str | None = typer.Option(None, "--address"),
) -> None:
    """Run the complete V3 Analysis Engine on Domain Transactions."""
    transactions = _domain_transactions(file)
    result = AnalysisEngine().analyze(transactions, address)
    paths = AnalysisExporter().export_all(result, _analysis_output_dir(file))
    typer.echo(f"Analysis: {paths['analysis']}")


if __name__ == "__main__":
    app()
