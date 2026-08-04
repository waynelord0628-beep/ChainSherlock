from pathlib import Path
import asyncio
import os
from datetime import datetime
from decimal import Decimal
import json
import shutil
from types import SimpleNamespace

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
from crypto_investigator.analyzers.models import FlowEdge, FlowNode, FlowResult
from crypto_investigator.domain.transaction import Direction
from crypto_investigator.graphs.export import GraphExporter
from crypto_investigator.graphs.factory import GraphFactory
from crypto_investigator.graphs.models import GraphFilterOptions
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.evidence import EvidenceManifest
from crypto_investigator.reports.export import ReportExportCoordinator
from crypto_investigator.investigation.feature_engine import InvestigationFeatureEngine
from crypto_investigator.investigation.investigation_result import InvestigationSettings
from crypto_investigator.investigation.export import InvestigationExporter
from crypto_investigator.labels.registry import LabelRegistry

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


def _graph_options(
    *,
    top_counterparties: int,
    max_nodes: int,
    max_edges: int,
    include_asset: list[str] | None,
    exclude_asset: list[str] | None,
    incoming_only: bool,
    outgoing_only: bool,
    date_from: datetime | None,
    date_to: datetime | None,
    sort_by: str,
    sort_asset: str | None,
) -> GraphFilterOptions:
    return GraphFilterOptions(
        top_counterparties=top_counterparties,
        maximum_nodes=max_nodes,
        maximum_edges=max_edges,
        include_assets=tuple(include_asset or ()),
        exclude_assets=tuple(exclude_asset or ()),
        incoming_only=incoming_only,
        outgoing_only=outgoing_only,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_asset=sort_asset,
    )


def _write_graph(analysis, chain: Chain, target: str | None, output: Path, options):
    graph = GraphFactory.create("address_flow").build(
        analysis,
        chain=chain,
        target_address=target,
        options=options,
    )
    paths = GraphExporter().export_all(graph, output, options)
    typer.echo(f"Graph JSON: {paths['json']}")
    typer.echo(f"GraphML: {paths['graphml']}")
    typer.echo(f"HTML: {paths['html']}")


def _analysis_from_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    flow = value["flow"]
    flow_result = FlowResult(
        nodes=tuple(FlowNode(item["address"]) for item in flow["nodes"]),
        edges=tuple(
            FlowEdge(
                source=item["source"],
                target=item["target"],
                direction=Direction(item["direction"]),
                weight=Decimal(item["weight"]),
                asset=item["asset"],
                timestamp=(
                    datetime.fromisoformat(item["timestamp"])
                    if item.get("timestamp")
                    else None
                ),
                tx_hash=item["tx_hash"],
            )
            for item in flow["edges"]
        ),
    )
    metadata = dict(value.get("metadata", {}))
    provider_errors_path = path.with_name("provider_errors.json")
    provider_status_path = path.with_name("provider_status.json")
    if provider_errors_path.exists():
        metadata["provider_errors"] = json.loads(
            provider_errors_path.read_text(encoding="utf-8")
        )
    if provider_status_path.exists():
        statuses = json.loads(provider_status_path.read_text(encoding="utf-8"))
        metadata["missing_data"] = sorted(
            {
                category
                for status in statuses
                for category in status.get("missing_data", [])
            }
        )
    return SimpleNamespace(
        flow=flow_result,
        summary=SimpleNamespace(
            transaction_count=value["summary"]["transaction_count"]
        ),
        metadata=metadata,
        warnings=tuple(value.get("warnings", ())),
    )


@app.command("graph-file")
def graph_file(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    target: str = typer.Option(..., "--target"),
    top_counterparties: int = typer.Option(30, "--top-counterparties", min=0),
    max_nodes: int = typer.Option(100, "--max-nodes", min=1),
    max_edges: int = typer.Option(200, "--max-edges", min=0),
    include_asset: list[str] | None = typer.Option(None, "--include-asset"),
    exclude_asset: list[str] | None = typer.Option(None, "--exclude-asset"),
    incoming_only: bool = typer.Option(False, "--incoming-only"),
    outgoing_only: bool = typer.Option(False, "--outgoing-only"),
    date_from: datetime | None = typer.Option(None, "--date-from"),
    date_to: datetime | None = typer.Option(None, "--date-to"),
    sort_by: str = typer.Option("transactions", "--sort-by"),
    sort_asset: str | None = typer.Option(None, "--sort-asset"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Build Graph JSON, GraphML, and offline HTML from a transaction file."""
    transactions = _domain_transactions(file)
    try:
        chain = (
            transactions[0].chain
            if transactions
            else Chain(detect_identifier(target).chain.value)
        )
        analysis = AnalysisEngine().analyze(transactions, target)
        options = _graph_options(
            top_counterparties=top_counterparties,
            max_nodes=max_nodes,
            max_edges=max_edges,
            include_asset=include_asset,
            exclude_asset=exclude_asset,
            incoming_only=incoming_only,
            outgoing_only=outgoing_only,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_asset=sort_asset,
        )
        _write_graph(
            analysis,
            chain,
            target,
            output or Path("output") / file.stem,
            options,
        )
    except (ValueError, InvalidIdentifierError) as error:
        typer.echo(f"Graph error: {error}", err=True)
        raise typer.Exit(code=2) from error


@app.command("graph-address")
def graph_address(
    address: str = typer.Argument(...),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    cache_ttl: int = typer.Option(86400, "--cache-ttl", min=1),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    top_counterparties: int = typer.Option(30, "--top-counterparties", min=0),
    max_nodes: int = typer.Option(100, "--max-nodes", min=1),
    max_edges: int = typer.Option(200, "--max-edges", min=0),
    include_asset: list[str] | None = typer.Option(None, "--include-asset"),
    exclude_asset: list[str] | None = typer.Option(None, "--exclude-asset"),
    incoming_only: bool = typer.Option(False, "--incoming-only"),
    outgoing_only: bool = typer.Option(False, "--outgoing-only"),
    date_from: datetime | None = typer.Option(None, "--date-from"),
    date_to: datetime | None = typer.Option(None, "--date-to"),
    sort_by: str = typer.Option("transactions", "--sort-by"),
    sort_asset: str | None = typer.Option(None, "--sort-asset"),
    output: Path = typer.Option(Path("output/provider_graph"), "--output"),
) -> None:
    """Build Graph exports after the existing V4 address analysis workflow."""
    try:
        detected = detect_identifier(address)
        selected_chain = chain or Chain(detected.chain.value)
        settings = load_config()
        settings.pagination.max_pages = max_pages
        settings.pagination.max_records = max_records
        asyncio.run(
            analyze_provider_identifier(
                identifier=detected.value,
                chain=selected_chain,
                kind="address",
                settings=settings,
                output_dir=output,
                provider=provider,
                refresh=refresh,
                cache_ttl=cache_ttl,
            )
        )
        options = _graph_options(
            top_counterparties=top_counterparties,
            max_nodes=max_nodes,
            max_edges=max_edges,
            include_asset=include_asset,
            exclude_asset=exclude_asset,
            incoming_only=incoming_only,
            outgoing_only=outgoing_only,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_asset=sort_asset,
        )
        _write_graph(
            _analysis_from_json(output / "analysis.json"),
            selected_chain,
            detected.value,
            output,
            options,
        )
    except (ValueError, KeyError, InvalidIdentifierError) as error:
        typer.echo(f"Graph error: {error}", err=True)
        raise typer.Exit(code=2) from error


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


def _report_graph(analysis, chain: Chain, target: str, output: Path, top: int):
    graph = GraphFactory.create("address_flow").build(
        analysis,
        chain=chain,
        target_address=target,
        options=GraphFilterOptions(top_counterparties=top),
    )
    GraphExporter().export_all(graph, output, GraphFilterOptions(top_counterparties=top))
    return graph


def _report_evidence(paths: tuple[Path, ...]):
    existing = tuple(path.resolve() for path in paths if path.exists())
    if not existing:
        return ()
    root = Path(os.path.commonpath([str(path.parent) for path in existing]))
    return EvidenceManifest().collect(existing, root=root)


def _export_report(
    analysis,
    graph,
    *,
    report_type: str,
    target: str,
    chain: Chain,
    output: Path,
    source_files: tuple[Path, ...] = (),
    requested_format: str = "all",
    language: str = "zh-TW",
    title: str = "ChainSherlock 區塊鏈幣流分析報告",
    report_id: str | None = None,
    timezone: str = "UTC",
    investigation=None,
) -> None:
    evidence_paths = (
        *source_files,
        *(output / name for name in (
            "analysis.json",
            "flow_graph.json",
            "provider_status.json",
            "provider_errors.json",
            "rejected_records.json",
        )),
    )
    document = ReportComposer().compose(
        analysis,
        graph=graph,
        investigation=investigation,
        target_address=target,
        chain=chain.value,
        source_type=report_type,
        source_files=tuple(str(item) for item in source_files),
        provider_status=_read_records(output / "provider_status.json"),
        provider_errors=_read_records(output / "provider_errors.json"),
        rejected_records=_read_records(output / "rejected_records.json"),
        evidence=_report_evidence(tuple(evidence_paths)),
        title=title,
        report_id=report_id,
        language=language,
        timezone=timezone,
        output_directory=str(output),
    )
    result = ReportExportCoordinator().export(document, output, requested_format)
    typer.echo(f"Report status: {result.status}")
    typer.echo(f"Report data: {output / 'report_data.json'}")


def _read_records(path: Path):
    if not path.exists():
        return ()
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _investigation_settings(
    dormant_days: int,
    funding_window_days: int,
    batch_window_minutes: int,
    timezone: str,
):
    return InvestigationSettings(
        dormant_days=dormant_days,
        funding_window_days=funding_window_days,
        batch_window_minutes=batch_window_minutes,
        timezone=timezone,
    )


def _investigation_labels(label_file: Path | None):
    return LabelRegistry.import_file(label_file).records if label_file else ()


@app.command("labels-import")
def labels_import(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path = typer.Option(Path("data/labels/labels.json"), "--output"),
) -> None:
    """Import deterministic local labels from CSV, Excel, or JSON."""
    registry = LabelRegistry.import_file(file)
    registry.write(output)
    typer.echo(f"Labels imported: {len(registry.records)}")
    typer.echo(f"Labels: {output}")


@app.command("labels-check")
def labels_check(
    address: str = typer.Argument(...),
    chain: Chain = typer.Option(..., "--chain"),
    label_file: Path = typer.Option(Path("data/labels/labels.json"), "--label-file"),
) -> None:
    """Check one normalized address against the local label registry."""
    registry = LabelRegistry.import_file(label_file)
    typer.echo(
        json.dumps(
            [AnalysisExporter.to_primitive(item) for item in registry.check(chain.value, address)],
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("investigate-file")
def investigate_file(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    target: str = typer.Option(..., "--target"),
    chain: Chain | None = typer.Option(None, "--chain"),
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
    label_file: Path | None = typer.Option(None, "--label-file"),
    dormant_days: int = typer.Option(30, "--dormant-days", min=1),
    funding_window_days: int = typer.Option(30, "--funding-window-days", min=1),
    batch_window_minutes: int = typer.Option(10, "--batch-window-minutes", min=1),
    output: Path = typer.Option(Path("output/investigation_file"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Run deterministic V6.5 investigation features on a transaction file."""
    transactions = _domain_transactions(file)
    selected_chain = chain or (
        transactions[0].chain if transactions else Chain(detect_identifier(target).chain.value)
    )
    analysis = AnalysisEngine().analyze(transactions, target)
    engine = InvestigationFeatureEngine(
        _investigation_settings(
            dormant_days, funding_window_days, batch_window_minutes, timezone
        )
    )
    result = engine.analyze(
        analysis, target, labels=_investigation_labels(label_file)
    )
    paths = InvestigationExporter().export_all(result, output)
    if report:
        AnalysisExporter().export_all(analysis, output)
        graph = _report_graph(analysis, selected_chain, target, output, 20)
        graph = engine.annotate_graph(graph, result)
        GraphExporter().export_all(graph, output, GraphFilterOptions(top_counterparties=20))
        _export_report(
            analysis,
            graph,
            report_type="file",
            target=target,
            chain=selected_chain,
            output=output,
            source_files=(file,),
            requested_format=format,
            timezone=timezone,
            investigation=result,
        )
    typer.echo(f"Investigation: {paths['investigation']}")


def _investigate_provider(
    identifier: str,
    chain: Chain,
    kind: str,
    provider: str | None,
    refresh: bool,
    max_pages: int,
    max_records: int,
    output: Path,
    settings: InvestigationSettings,
    labels,
    report: bool,
    requested_format: str,
):
    provider_settings = load_config()
    provider_settings.pagination.max_pages = max_pages
    provider_settings.pagination.max_records = max_records
    asyncio.run(
        analyze_provider_identifier(
            identifier=identifier,
            chain=chain,
            kind=kind,
            settings=provider_settings,
            output_dir=output,
            provider=provider,
            refresh=refresh,
        )
    )
    value = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    value.setdefault("metadata", {})["chain"] = chain.value
    feature_target = identifier
    if kind == "transaction" and value.get("flow", {}).get("edges"):
        feature_target = value["flow"]["edges"][0]["source"]
    engine = InvestigationFeatureEngine(settings)
    result = engine.analyze_public_mapping(value, feature_target, labels=labels)
    paths = InvestigationExporter().export_all(result, output)
    if report:
        graph_analysis = _analysis_from_json(output / "analysis.json")
        graph = _report_graph(graph_analysis, chain, feature_target, output, 20)
        graph = engine.annotate_graph(graph, result)
        GraphExporter().export_all(graph, output, GraphFilterOptions(top_counterparties=20))
        _export_report(
            value,
            graph,
            report_type="provider",
            target=feature_target,
            chain=chain,
            output=output,
            requested_format=requested_format,
            timezone=settings.timezone,
            investigation=result,
        )
    typer.echo(f"Investigation: {paths['investigation']}")


@app.command("investigate-address")
def investigate_address(
    address: str = typer.Argument(...),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
    label_file: Path | None = typer.Option(None, "--label-file"),
    dormant_days: int = typer.Option(30, "--dormant-days", min=1),
    funding_window_days: int = typer.Option(30, "--funding-window-days", min=1),
    batch_window_minutes: int = typer.Option(10, "--batch-window-minutes", min=1),
    output: Path = typer.Option(Path("output/investigation_address"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Run deterministic V6.5 investigation after Provider analysis."""
    detected = detect_identifier(address)
    selected_chain = chain or Chain(detected.chain.value)
    _investigate_provider(
        detected.value, selected_chain, "address", provider, refresh, max_pages,
        max_records, output,
        _investigation_settings(dormant_days, funding_window_days, batch_window_minutes, timezone),
        _investigation_labels(label_file), report, format,
    )


@app.command("investigate-tx")
def investigate_tx(
    tx_hash: str = typer.Argument(...),
    chain: Chain = typer.Option(..., "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
    label_file: Path | None = typer.Option(None, "--label-file"),
    dormant_days: int = typer.Option(30, "--dormant-days", min=1),
    funding_window_days: int = typer.Option(30, "--funding-window-days", min=1),
    batch_window_minutes: int = typer.Option(10, "--batch-window-minutes", min=1),
    output: Path = typer.Option(Path("output/investigation_tx"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Run deterministic V6.5 investigation for one Provider transaction."""
    _investigate_provider(
        tx_hash, chain, "transaction", provider, refresh, max_pages, max_records,
        output,
        _investigation_settings(dormant_days, funding_window_days, batch_window_minutes, timezone),
        _investigation_labels(label_file), report, format,
    )


@app.command("report-file")
def report_file(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    target: str = typer.Option(..., "--target"),
    format: str = typer.Option("all", "--format"),
    language: str = typer.Option("zh-TW", "--language"),
    title: str = typer.Option("ChainSherlock 區塊鏈幣流分析報告", "--title"),
    report_id: str | None = typer.Option(None, "--report-id"),
    output: Path | None = typer.Option(None, "--output"),
    include_graph: bool = typer.Option(True, "--include-graph/--no-graph"),
    top_counterparties: int = typer.Option(20, "--top-counterparties", min=0),
    timezone: str = typer.Option("UTC", "--timezone"),
) -> None:
    """Create a V6 report from a CSV or Excel transaction file."""
    transactions = _domain_transactions(file)
    try:
        chain = transactions[0].chain if transactions else Chain(detect_identifier(target).chain.value)
        destination = output or Path("output") / f"{file.stem}_report"
        analysis = AnalysisEngine().analyze(transactions, target)
        AnalysisExporter().export_all(analysis, destination)
        graph = _report_graph(analysis, chain, target, destination, top_counterparties) if include_graph else None
        investigation = InvestigationFeatureEngine().analyze(analysis, target)
        if graph is not None:
            graph = InvestigationFeatureEngine.annotate_graph(graph, investigation)
            GraphExporter().export_all(
                graph,
                destination,
                GraphFilterOptions(top_counterparties=top_counterparties),
            )
        _export_report(
            analysis,
            graph,
            report_type="file",
            target=target,
            chain=chain,
            output=destination,
            source_files=(file,),
            requested_format=format,
            language=language,
            title=title,
            report_id=report_id,
            timezone=timezone,
            investigation=investigation,
        )
    except (ValueError, InvalidIdentifierError) as error:
        typer.echo(f"Report error: {error}", err=True)
        raise typer.Exit(code=2) from error


def _provider_report(
    identifier: str,
    chain: Chain,
    kind: str,
    provider: str | None,
    refresh: bool,
    cache_ttl: int,
    max_pages: int,
    max_records: int,
    output: Path,
    requested_format: str,
    language: str,
    title: str,
    report_id: str | None,
    include_graph: bool,
    top_counterparties: int,
    timezone: str,
) -> None:
    settings = load_config()
    settings.pagination.max_pages = max_pages
    settings.pagination.max_records = max_records
    asyncio.run(
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
    graph_analysis = _analysis_from_json(output / "analysis.json")
    report_analysis = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    investigation = InvestigationFeatureEngine().analyze_public_mapping(
        report_analysis, identifier
    )
    graph = _report_graph(graph_analysis, chain, identifier, output, top_counterparties) if include_graph else None
    if graph is not None:
        graph = InvestigationFeatureEngine.annotate_graph(graph, investigation)
        GraphExporter().export_all(
            graph,
            output,
            GraphFilterOptions(top_counterparties=top_counterparties),
        )
    _export_report(
        report_analysis,
        graph,
        report_type="provider",
        target=identifier,
        chain=chain,
        output=output,
        requested_format=requested_format,
        language=language,
        title=title,
        report_id=report_id,
        timezone=timezone,
        investigation=investigation,
    )


@app.command("report-address")
def report_address(
    address: str = typer.Argument(...),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    refresh: bool = typer.Option(False, "--refresh"),
    cache_ttl: int = typer.Option(86400, "--cache-ttl", min=1),
    max_pages: int = typer.Option(100, "--max-pages", min=1),
    max_records: int = typer.Option(100000, "--max-records", min=1),
    format: str = typer.Option("all", "--format"),
    language: str = typer.Option("zh-TW", "--language"),
    title: str = typer.Option("ChainSherlock 區塊鏈幣流分析報告", "--title"),
    report_id: str | None = typer.Option(None, "--report-id"),
    output: Path = typer.Option(Path("output/address_report"), "--output"),
    include_graph: bool = typer.Option(True, "--include-graph/--no-graph"),
    top_counterparties: int = typer.Option(20, "--top-counterparties", min=0),
    timezone: str = typer.Option("UTC", "--timezone"),
) -> None:
    """Create a V6 report from the existing provider workflow."""
    detected = detect_identifier(address)
    _provider_report(
        detected.value, chain or Chain(detected.chain.value), "address", provider,
        refresh, cache_ttl, max_pages, max_records, output, format, language,
        title, report_id, include_graph, top_counterparties, timezone,
    )


@app.command("report-tx")
def report_tx(
    tx_hash: str = typer.Argument(...),
    chain: Chain = typer.Option(..., "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    format: str = typer.Option("all", "--format"),
    language: str = typer.Option("zh-TW", "--language"),
    title: str = typer.Option("ChainSherlock 區塊鏈幣流分析報告", "--title"),
    report_id: str | None = typer.Option(None, "--report-id"),
    output: Path = typer.Option(Path("output/transaction_report"), "--output"),
    include_graph: bool = typer.Option(True, "--include-graph/--no-graph"),
    top_counterparties: int = typer.Option(20, "--top-counterparties", min=0),
    timezone: str = typer.Option("UTC", "--timezone"),
) -> None:
    """Create a V6 report for one provider transaction."""
    _provider_report(
        tx_hash, chain, "transaction", provider, False, 86400, 100, 100000,
        output, format, language, title, report_id, include_graph,
        top_counterparties, timezone,
    )


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
