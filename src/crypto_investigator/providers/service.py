from pathlib import Path
from dataclasses import replace

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.config import Settings
from crypto_investigator.core.pipeline import DataPipeline
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.importers.provider import ProviderRecordImporter
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.factory import ProviderFactory
from crypto_investigator.providers.output import write_provider_outputs
from crypto_investigator.providers.selection import ProviderSelectionPolicy


async def analyze_provider_identifier(
    *,
    identifier: str,
    chain: Chain,
    kind: str,
    settings: Settings,
    output_dir: Path,
    provider: str | None = None,
    refresh: bool = False,
    cache_ttl: int | None = None,
) -> dict[str, Path]:
    registry = ProviderFactory.create_registry(
        settings, refresh=refresh, cache_ttl=cache_ttl
    )
    collector = ProviderCollector(ProviderSelectionPolicy(registry, settings))
    if kind == "address":
        collection = await collector.collect_address(
            chain, identifier, provider=provider
        )
    else:
        collection = await collector.collect_transaction(
            chain, identifier, provider=provider
        )
    provider_pipeline = ProviderRecordImporter().to_domain_partial(
        collection.records, DataPipeline()
    )
    transactions = provider_pipeline.transactions
    analysis = AnalysisEngine().analyze(
        transactions, identifier if kind == "address" else None
    )
    rejected_count = len(provider_pipeline.rejected_records)
    completeness = (
        "failed"
        if not transactions
        and (
            rejected_count
            or collection.errors
            or any(result.missing_data for result in collection.results)
        )
        else (
            "partial"
            if rejected_count
            or collection.errors
            or any(
                result.completeness.value == "partial"
                for result in collection.results
            )
            else "complete"
        )
    )
    analysis = replace(
        analysis,
        metadata={
            **analysis.metadata,
            "rejected_record_count": rejected_count,
            "completeness": completeness,
        },
        warnings=(
            *analysis.warnings,
            *((f"rejected_provider_records={rejected_count}",) if rejected_count else ()),
        ),
    )
    paths = AnalysisExporter().export_all(analysis, output_dir)
    paths.update(
        write_provider_outputs(
            output_dir,
            collection,
            rejected_records=provider_pipeline.rejected_records,
            analysis_completeness=completeness,
        )
    )
    return paths
