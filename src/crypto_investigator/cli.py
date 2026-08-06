from pathlib import Path
import asyncio
import os
from collections.abc import Mapping
from dataclasses import replace
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
from crypto_investigator.domain.scope import (
    AnalysisScope,
    PaginationPolicy,
    ScopeType,
)
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
from crypto_investigator.labels.source_registry import MultiSourceLabelRegistry
from crypto_investigator.ai.settings import AISettings
from crypto_investigator.narratives.engine import NarrativeEngine
from crypto_investigator.narratives.export import NarrativeExporter
from crypto_investigator.narratives.models import NarrativeInput, NarrativeResult
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.reports.offline import OfflineReportComposer
from crypto_investigator.reports.json_exporter import read_report_data
from crypto_investigator.domain.fund_trace_engine import investigate_fund_trace
from crypto_investigator.domain.fund_tracing import (
    SeedType,
    TraceDirection,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.graphs.trace_adapter import trace_result_to_graph
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.multihop import collect_multihop_edges
from crypto_investigator.providers.selection import ProviderSelectionPolicy
from crypto_investigator.reports.multihop import compose_multihop_report

app = typer.Typer(help="ChainSherlock: local-first blockchain transaction investigation toolkit.")


def _provider_scope(
    scope_type: ScopeType,
    max_pages: int | None,
    max_records: int | None,
    *,
    timezone: str,
    settings,
) -> AnalysisScope:
    if scope_type is ScopeType.QUICK_PREVIEW:
        return AnalysisScope(
            scope_type=scope_type,
            timezone=timezone,
            pagination_policy=PaginationPolicy.BOUNDED,
            max_pages=max_pages or settings.pagination.max_pages,
            max_records=max_records or settings.pagination.max_records,
        )
    if max_pages is not None or max_records is not None:
        raise typer.BadParameter(
            "--max-pages/--max-records are only valid with --scope-type quick_preview"
        )
    return AnalysisScope(
        scope_type=scope_type,
        timezone=timezone,
        pagination_policy=PaginationPolicy.TO_PROVIDER_END,
    )


def _case_repository(case_root: Path):
    from crypto_investigator.cases import CaseRepository

    return CaseRepository(case_root)


@app.command("ui")
def ui_command(
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
) -> None:
    """Launch the local PySide6 case investigation workbench."""
    from crypto_investigator.ui import launch_ui

    raise typer.Exit(launch_ui(case_root))


@app.command("case-result")
def case_result_command(
    case_id: str,
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Aggregate verified case artifacts into deterministic CaseResult JSON."""
    from crypto_investigator.application import CaseResultService

    result = CaseResultService(_case_repository(case_root)).build_case_result(case_id)
    text = result.model_dump_json(indent=2)
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(text)


@app.command("case-report")
def case_report_command(
    case_id: str,
    format: str = typer.Option("all", "--format"),
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
) -> None:
    """Generate a versioned deterministic case report."""
    from crypto_investigator.application import CaseReportService, CaseResultService

    repository = _case_repository(case_root)
    result = CaseResultService(repository).build_case_result(case_id)
    summary = CaseReportService(repository).generate(result, format)
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))


@app.command("case-export")
def case_export_command(
    case_id: str,
    mode: str = typer.Option("full", "--mode"),
    output: Path = typer.Option(Path("case.chainsherlock-case.zip"), "--output"),
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
) -> None:
    """Export a full, report-only, or de-identified case package."""
    from crypto_investigator.application import CasePackageService

    path = CasePackageService(_case_repository(case_root)).export_case_package(
        case_id, output, mode
    )
    typer.echo(str(path))


@app.command("case-import")
def case_import_command(
    package: Path,
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
) -> None:
    """Validate and atomically import a case package."""
    from crypto_investigator.application import CasePackageService

    record = CasePackageService(_case_repository(case_root)).import_case_package(package)
    typer.echo(record.case_id)


@app.command("case-package-validate")
def case_package_validate_command(
    package: Path,
    case_root: Path = typer.Option(Path("cases"), "--case-root"),
) -> None:
    """Validate a case package without importing it."""
    from crypto_investigator.application import CasePackageService

    manifest = CasePackageService(_case_repository(case_root)).validate_case_package(
        package
    )
    typer.echo(manifest.model_dump_json(indent=2))


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
    max_pages: int | None,
    max_records: int | None,
    cache_ttl: int,
    refresh: bool,
    scope_type: ScopeType = ScopeType.FULL_HISTORY,
    timezone: str = "UTC",
) -> None:
    settings = load_config()
    settings.cache.ttl_seconds = cache_ttl
    scope = _provider_scope(
        scope_type, max_pages, max_records, timezone=timezone, settings=settings
    )
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
                analysis_scope=scope,
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
    scope_type: ScopeType = typer.Option(ScopeType.FULL_HISTORY, "--scope-type"),
    max_pages: int | None = typer.Option(None, "--max-pages", min=1),
    max_records: int | None = typer.Option(None, "--max-records", min=1),
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
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
        scope_type,
        timezone,
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
    narrative=None,
) -> None:
    evidence_paths = (
        *source_files,
        *(output / name for name in (
            "analysis.json",
            "flow_graph.json",
            "provider_status.json",
            "provider_errors.json",
            "rejected_records.json",
            "investigation_evidence.json",
            *(
                (
                    "narrative_input.json",
                    "narrative.json",
                    "narrative_validation.json",
                    "ai_usage.json",
                    "prompt_manifest.json",
                    "ai_status.json",
                    "ai_errors.json",
                )
                if narrative is not None
                else ()
            ),
        )),
    )
    document = ReportComposer().compose(
        analysis,
        graph=graph,
        investigation=investigation,
        narrative=narrative,
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


@app.command("labels-build-registry")
def labels_build_registry(
    dune_cex: Path | None = typer.Option(
        None, "--dune-cex", exists=True, dir_okay=False, readable=True
    ),
    dune_owners: Path | None = typer.Option(
        None, "--dune-owners", exists=True, dir_okay=False, readable=True
    ),
    ofac: Path | None = typer.Option(
        None, "--ofac", exists=True, dir_okay=False, readable=True
    ),
    output: Path = typer.Option(Path("data/labels/labels.db"), "--output"),
) -> None:
    """Build an evidence-preserving local label database from curated snapshots."""
    inputs = (
        (dune_cex, MultiSourceLabelRegistry.import_dune_cex_csv),
        (dune_owners, MultiSourceLabelRegistry.import_dune_owner_csv),
        (ofac, MultiSourceLabelRegistry.import_ofac_digital_currency_csv),
    )
    registries = tuple(importer(path) for path, importer in inputs if path)
    if not registries:
        raise typer.BadParameter(
            "Provide at least one of --dune-cex, --dune-owners, or --ofac"
        )
    registry = MultiSourceLabelRegistry.combine(*registries)
    registry.write_sqlite(output)
    typer.echo(f"Label records: {len(registry.records)}")
    typer.echo(f"Snapshots: {len(registry.snapshots)}")
    typer.echo(f"Registry: {output}")


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


def _ai_settings(ai, provider, model, max_tokens, max_input_chars, privacy_mode):
    base = AISettings.from_env()
    return AISettings(
        enabled=bool(ai),
        provider=provider or base.provider,
        model=model or base.model,
        api_key=base.api_key,
        base_url=base.base_url,
        timeout_seconds=base.timeout_seconds,
        max_output_tokens=max_tokens,
        max_input_characters=max_input_chars,
        privacy_mode=privacy_mode,
    )


def _run_narrative(
    investigation,
    output,
    *,
    ai,
    ai_provider,
    ai_model,
    ai_max_tokens,
    ai_max_input_chars,
    privacy_mode,
    language,
    tone,
    section,
    save_prompt,
    ai_refresh=False,
    ai_no_cache=False,
    prompt_mode="standard",
):
    result = NarrativeEngine().run(
        investigation,
        output,
        settings=_ai_settings(
            ai, ai_provider, ai_model, ai_max_tokens, ai_max_input_chars, privacy_mode
        ),
        requested=ai,
        language=language,
        tone=tone,
        sections=tuple(section),
        save_prompt=save_prompt,
        use_cache=not ai_no_cache,
        refresh=ai_refresh,
        prompt_mode=prompt_mode,
    )
    typer.echo(f"Narrative: {output / 'narrative.json'}")
    return result


@app.command("narrate-investigation")
def narrate_investigation(
    investigation_json: Path = typer.Argument(..., exists=True, dir_okay=False),
    ai: bool = typer.Option(False, "--ai/--no-ai"),
    ai_provider: str | None = typer.Option(None, "--ai-provider"),
    ai_model: str | None = typer.Option(None, "--ai-model"),
    ai_refresh: bool = typer.Option(False, "--ai-refresh"),
    ai_no_cache: bool = typer.Option(False, "--ai-no-cache"),
    ai_max_tokens: int = typer.Option(2000, "--ai-max-tokens", min=1, max=8000),
    ai_max_input_chars: int = typer.Option(100000, "--ai-max-input-chars", min=1000, max=500000),
    privacy_mode: str = typer.Option("standard", "--privacy-mode"),
    language: str = typer.Option("zh-TW", "--language"),
    tone: str = typer.Option("professional", "--tone"),
    section: list[str] = typer.Option([], "--section"),
    save_prompt: bool = typer.Option(False, "--save-prompt"),
    prompt_mode: str = typer.Option("standard", "--prompt-mode"),
    output: Path = typer.Option(Path("output/narrative"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Generate an offline narrative/report from a public V6.5/V7 artifact."""
    public_input = None
    narrative = None
    try:
        investigation = InvestigationExporter().read(investigation_json)
    except Exception:
        artifact = NarrativeExporter.read_any(investigation_json)
        if isinstance(artifact, NarrativeInput):
            public_input = artifact
            narrative = NarrativeEngine().run_input(
                public_input, output,
                settings=_ai_settings(
                    ai, ai_provider, ai_model, ai_max_tokens,
                    ai_max_input_chars, privacy_mode,
                ),
                requested=ai, save_prompt=save_prompt,
                use_cache=not ai_no_cache, refresh=ai_refresh,
                prompt_mode=prompt_mode,
            )
        elif isinstance(artifact, NarrativeResult):
            narrative = artifact
            sibling_input = investigation_json.with_name(
                "narrative_input.json"
            )
            if sibling_input.is_file():
                public_input = NarrativeExporter().read_input(sibling_input)
            NarrativeExporter().write(narrative, output / "narrative.json")
        else:
            raise typer.BadParameter("Unsupported public investigation artifact")
    else:
        public_input = NarrativeInputBuilder().build(
            investigation, language=language, tone=tone,
            requested_sections=tuple(section) or NarrativeInputBuilder().build(investigation).requested_sections,
        )
        narrative = _run_narrative(
            investigation, output, ai=ai, ai_provider=ai_provider, ai_model=ai_model,
            ai_max_tokens=ai_max_tokens, ai_max_input_chars=ai_max_input_chars,
            privacy_mode=privacy_mode, language=language, tone=tone, section=section,
            save_prompt=save_prompt, ai_refresh=ai_refresh, ai_no_cache=ai_no_cache,
            prompt_mode=prompt_mode,
        )
    if report:
        base_report_path = investigation_json.with_name("report_data.json")
        base_report = (
            read_report_data(base_report_path)
            if base_report_path.is_file()
            else None
        )
        document = OfflineReportComposer().compose(
            narrative,
            public_input,
            base_report=base_report,
            output_directory=str(output),
        )
        exported = ReportExportCoordinator().export(document, output, format)
        typer.echo(f"Report status: {exported.status}")


@app.command("narrate-file")
def narrate_file(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    target: str = typer.Option(..., "--target"),
    chain: Chain | None = typer.Option(None, "--chain"),
    ai: bool = typer.Option(False, "--ai/--no-ai"),
    ai_provider: str | None = typer.Option(None, "--ai-provider"),
    ai_model: str | None = typer.Option(None, "--ai-model"),
    ai_refresh: bool = typer.Option(False, "--ai-refresh"),
    ai_no_cache: bool = typer.Option(False, "--ai-no-cache"),
    ai_max_tokens: int = typer.Option(2000, "--ai-max-tokens", min=1, max=8000),
    ai_max_input_chars: int = typer.Option(100000, "--ai-max-input-chars", min=1000, max=500000),
    privacy_mode: str = typer.Option("standard", "--privacy-mode"),
    language: str = typer.Option("zh-TW", "--language"),
    tone: str = typer.Option("professional", "--tone"),
    section: list[str] = typer.Option([], "--section"),
    save_prompt: bool = typer.Option(False, "--save-prompt"),
    prompt_mode: str = typer.Option("standard", "--prompt-mode"),
    output: Path = typer.Option(Path("output/narrative_file"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Run file investigation and generate a grounded narrative."""
    transactions = _domain_transactions(file)
    selected_chain = chain or (transactions[0].chain if transactions else Chain(detect_identifier(target).chain.value))
    analysis = AnalysisEngine().analyze(transactions, target)
    investigation = InvestigationFeatureEngine().analyze(analysis, target)
    InvestigationExporter().export_all(investigation, output)
    narrative = _run_narrative(
        investigation, output, ai=ai, ai_provider=ai_provider, ai_model=ai_model,
        ai_max_tokens=ai_max_tokens, ai_max_input_chars=ai_max_input_chars,
        privacy_mode=privacy_mode, language=language, tone=tone, section=section,
        save_prompt=save_prompt,
        ai_refresh=ai_refresh, ai_no_cache=ai_no_cache,
        prompt_mode=prompt_mode,
    )
    if report:
        AnalysisExporter().export_all(analysis, output)
        graph = _report_graph(analysis, selected_chain, target, output, 20)
        _export_report(
            analysis, graph, report_type="file", target=target, chain=selected_chain,
            output=output, source_files=(file,), requested_format=format,
            language=language, investigation=investigation, narrative=narrative,
        )


@app.command("narrate-address")
def narrate_address(
    address: str = typer.Argument(...),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    ai: bool = typer.Option(False, "--ai/--no-ai"),
    ai_provider: str | None = typer.Option(None, "--ai-provider"),
    ai_model: str | None = typer.Option(None, "--ai-model"),
    ai_refresh: bool = typer.Option(False, "--ai-refresh"),
    ai_no_cache: bool = typer.Option(False, "--ai-no-cache"),
    ai_max_tokens: int = typer.Option(2000, "--ai-max-tokens", min=1, max=8000),
    ai_max_input_chars: int = typer.Option(100000, "--ai-max-input-chars", min=1000, max=500000),
    privacy_mode: str = typer.Option("standard", "--privacy-mode"),
    language: str = typer.Option("zh-TW", "--language"),
    tone: str = typer.Option("professional", "--tone"),
    section: list[str] = typer.Option([], "--section"),
    save_prompt: bool = typer.Option(False, "--save-prompt"),
    prompt_mode: str = typer.Option("standard", "--prompt-mode"),
    output: Path = typer.Option(Path("output/narrative_address"), "--output"),
    report: bool = typer.Option(False, "--report"),
    format: str = typer.Option("all", "--format"),
) -> None:
    """Run Provider investigation and generate a grounded narrative."""
    del report, format
    detected = detect_identifier(address)
    selected_chain = chain or Chain(detected.chain.value)
    _investigate_provider(
        detected.value, selected_chain, "address", provider, ai_refresh, 100, 100000,
        output, InvestigationSettings(), (), False, "all",
    )
    investigation = InvestigationExporter().read(output / "investigation.json")
    _run_narrative(
        investigation, output, ai=ai, ai_provider=ai_provider, ai_model=ai_model,
        ai_max_tokens=ai_max_tokens, ai_max_input_chars=ai_max_input_chars,
        privacy_mode=privacy_mode, language=language, tone=tone, section=section,
        save_prompt=save_prompt,
        ai_refresh=ai_refresh, ai_no_cache=ai_no_cache,
        prompt_mode=prompt_mode,
    )


@app.command("validate-ai")
def validate_ai(
    investigation_json: Path = typer.Argument(..., exists=True, dir_okay=False),
    provider: str = typer.Option("openai-compatible", "--provider"),
    model: str = typer.Option(..., "--model"),
    runs: int = typer.Option(3, "--runs", min=1, max=10),
    privacy_mode: str = typer.Option("standard", "--privacy-mode"),
    prompt_mode: str = typer.Option("compact", "--prompt-mode"),
    max_output_tokens: int = typer.Option(
        3000, "--max-output-tokens", min=1, max=8000
    ),
    max_retries: int = typer.Option(1, "--max-retries", min=0, max=1),
    cache: bool = typer.Option(True, "--cache/--no-cache"),
    output: Path = typer.Option(Path("output/real_ai_validation"), "--output"),
) -> None:
    """Explicitly run a safe, human-triggered real-model validation."""
    settings = AISettings.from_env()
    if not settings.api_key:
        raise typer.BadParameter(
            "CHAINSHERLOCK_AI_API_KEY is not configured; no external request was made"
        )
    settings = AISettings(
        enabled=True, provider=provider, model=model, api_key=settings.api_key,
        base_url=settings.base_url, timeout_seconds=settings.timeout_seconds,
        max_output_tokens=max_output_tokens,
        max_input_characters=settings.max_input_characters,
        privacy_mode=privacy_mode,
        max_retries=max_retries,
        reasoning_effort=settings.reasoning_effort,
    )
    investigation = InvestigationExporter().read(investigation_json)
    records = []
    signatures = []
    for index in range(runs):
        run_output = output / f"run_{index + 1}"
        result = NarrativeEngine().run(
            investigation, run_output, settings=settings, requested=True,
            refresh=False, use_cache=cache,
            prompt_mode=prompt_mode,
        )
        status = json.loads((run_output / "ai_status.json").read_text(encoding="utf-8"))
        usage = json.loads((run_output / "ai_usage.json").read_text(encoding="utf-8"))
        response_metadata = json.loads(
            (run_output / "ai_response_metadata.json").read_text(encoding="utf-8")
        )
        signature = {
            "claim_count": len(result.claims),
            "section_count": sum(
                getattr(result, name) is not None
                for name in result.__dataclass_fields__
                if name.endswith(("summary", "profile", "narrative", "explanations", "leads", "limitations", "conclusion"))
            ),
            "citations": [item.evidence_id for item in result.citations],
            "numeric_values": [value for claim in result.claims for value in claim.numeric_values],
        }
        signatures.append(signature)
        model_parse_succeeded = (
            status["status"] == "complete" and not status["fallback_used"]
        )
        http_status = response_metadata.get("http_status")
        model_request_succeeded = (
            isinstance(http_status, int) and 200 <= http_status < 300
        )
        model_output_received = bool(response_metadata.get("content_present"))
        records.append({
            "run": index + 1,
            "model_request_succeeded": model_request_succeeded,
            "model_output_received": model_output_received,
            "model_output_parse_succeeded": model_parse_succeeded,
            "model_output_schema_succeeded": model_parse_succeeded,
            "model_output_validation_succeeded": (
                model_parse_succeeded and status["validation_passed"]
            ),
            "model_finish_reason": response_metadata.get("finish_reason"),
            "model_usage_received": bool(response_metadata.get("usage")),
            "validated_source": (
                "model_output" if model_parse_succeeded else "deterministic_fallback"
            ),
            "json_parse_success": model_parse_succeeded,
            "schema_success": model_parse_succeeded and status["validation_passed"],
            "hallucination_validation": status["validation_passed"],
            "numeric_validation": status["validation_passed"],
            "citation_validation": status["validation_passed"],
            "candidate_preserved": status["validation_passed"],
            "partial_preserved": status["validation_passed"],
            "banned_wording_blocked": status["validation_passed"],
            "fallback_used": status["fallback_used"],
            "usage": usage,
            "signature": signature,
        })
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider, "model": model, "runs": runs,
        "privacy_mode": privacy_mode, "prompt_mode": prompt_mode,
        "max_output_tokens": max_output_tokens,
        "max_retries": max_retries,
        "cache_enabled": cache,
        "run_to_run_consistent": all(item == signatures[0] for item in signatures),
        "results": records,
        "api_key_included": False,
    }
    (output / "real_ai_validation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    typer.echo(f"AI validation: {output / 'real_ai_validation.json'}")


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
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
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
    max_pages: int | None,
    max_records: int | None,
    output: Path,
    requested_format: str,
    language: str,
    title: str,
    report_id: str | None,
    include_graph: bool,
    top_counterparties: int,
    timezone: str,
    scope_type: ScopeType = ScopeType.FULL_HISTORY,
) -> None:
    settings = load_config()
    scope = _provider_scope(
        scope_type, max_pages, max_records, timezone=timezone, settings=settings
    )
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
            analysis_scope=scope,
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
    scope_type: ScopeType = typer.Option(ScopeType.FULL_HISTORY, "--scope-type"),
    max_pages: int | None = typer.Option(None, "--max-pages", min=1),
    max_records: int | None = typer.Option(None, "--max-records", min=1),
    format: str = typer.Option("all", "--format"),
    language: str = typer.Option("zh-TW", "--language"),
    title: str = typer.Option("ChainSherlock 區塊鏈幣流分析報告", "--title"),
    report_id: str | None = typer.Option(None, "--report-id"),
    output: Path = typer.Option(Path("output/address_report"), "--output"),
    include_graph: bool = typer.Option(True, "--include-graph/--no-graph"),
    top_counterparties: int = typer.Option(20, "--top-counterparties", min=0),
    timezone: str = typer.Option("Asia/Taipei", "--timezone"),
) -> None:
    """Create a V6 report from the existing provider workflow."""
    detected = detect_identifier(address)
    _provider_report(
        detected.value, chain or Chain(detected.chain.value), "address", provider,
        refresh, cache_ttl, max_pages, max_records, output, format, language,
        title, report_id, include_graph, top_counterparties, timezone, scope_type,
    )


@app.command("trace-address")
def trace_address(
    address: str = typer.Argument(..., help="Seed address."),
    chain: Chain | None = typer.Option(None, "--chain"),
    provider: str | None = typer.Option(None, "--provider"),
    assets: str = typer.Option("USDT,TRX", "--assets"),
    depth: int = typer.Option(3, "--depth", min=1, max=5),
    direction: TraceDirection = typer.Option(
        TraceDirection.BIDIRECTIONAL, "--direction"
    ),
    minimum_amount: str = typer.Option("0.01", "--minimum-amount"),
    max_address_queries: int = typer.Option(20, "--max-address-queries", min=1),
    max_pages_per_address: int = typer.Option(
        10, "--max-pages-per-address", min=1
    ),
    max_records_per_address: int = typer.Option(
        2000, "--max-records-per-address", min=1
    ),
    labels: Path | None = typer.Option(None, "--labels", exists=True),
    output: Path = typer.Option(Path("output/multihop_trace"), "--output"),
    config: Path = typer.Option(Path("config/default.yaml"), "--config", exists=True),
) -> None:
    """Run budgeted 1-5 hop deterministic tracing and export graph/report artifacts."""

    detected = detect_identifier(address)
    selected_chain = chain or Chain(detected.chain.value)
    selected_assets = tuple(
        dict.fromkeys(item.strip() for item in assets.split(",") if item.strip())
    )
    if not selected_assets:
        raise typer.BadParameter("--assets requires at least one asset")
    try:
        parsed_minimum_amount = Decimal(minimum_amount)
    except Exception as error:
        raise typer.BadParameter("--minimum-amount must be numeric") from error
    if parsed_minimum_amount < 0:
        raise typer.BadParameter("--minimum-amount cannot be negative")
    settings = load_config(config)
    registry = ProviderFactory.create_registry(settings)
    collector = ProviderCollector(ProviderSelectionPolicy(registry, settings))

    async def fetch(
        identifier: str,
        start_cursors: Mapping[str, str],
        completed_capabilities: frozenset[str],
    ):
        return await collector.collect_address(
            selected_chain,
            identifier,
            provider=provider,
            provider_options={
                "max_pages": max_pages_per_address,
                "max_records": max_records_per_address,
                "start_cursors": dict(start_cursors),
                "completed_capabilities": tuple(completed_capabilities),
            },
        )

    scope = TraceScope(
        scope_type="bounded_multihop",
        max_depth=depth,
        max_nodes=max_address_queries,
        max_records=max_address_queries * max_records_per_address,
        min_material_amount=parsed_minimum_amount,
        asset_filters=selected_assets,
        direction=direction,
        timezone="Asia/Taipei",
    )
    seed = TraceSeed(
        SeedType.ADDRESS,
        detected.value,
        selected_chain.value,
        None,
        ("SEED-USER-INPUT",),
    )
    collected = asyncio.run(
        collect_multihop_edges(
            seed=seed,
            scope=scope,
            fetch_address=fetch,
            max_address_queries=max_address_queries,
        )
    )
    label_registry = LabelRegistry.import_file(labels) if labels else LabelRegistry()
    result, _ = investigate_fund_trace(
        run_id=f"TRACE-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        seed=seed,
        scope=scope,
        available_edges=collected.edges,
        labels=label_registry,
    )
    if collected.status is not TraceRunStatus.COMPLETED:
        result = replace(
            result,
            status=collected.status,
            limitations=tuple(
                dict.fromkeys((*result.limitations, *collected.limitations))
            ),
        )

    output.mkdir(parents=True, exist_ok=True)
    (output / "trace_result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    GraphExporter().export_all(trace_result_to_graph(result), output)
    exported = ReportExportCoordinator().export(
        compose_multihop_report(result),
        output,
        "all",
    )
    typer.echo(
        json.dumps(
            {
                "status": result.status.value,
                "address_queries": collected.address_query_count,
                "provider_pages": collected.provider_page_count,
                "trace_edges": len(result.edges),
                "patterns": len(result.patterns),
                "off_ramp_candidates": len(result.off_ramp_candidates),
                "report_export": exported.status,
            },
            ensure_ascii=False,
            indent=2,
        )
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
