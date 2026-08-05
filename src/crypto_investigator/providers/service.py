from pathlib import Path
from dataclasses import replace

from crypto_investigator.application.analysis_scope import (
    apply_scope,
    build_time_scope_result,
)
from crypto_investigator.application.first_hop_product import (
    FirstHopGoal,
    build_first_hop_product,
    write_first_hop_product,
)
from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.config import Settings
from crypto_investigator.core.pipeline import DataPipeline
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.domain.scope import (
    AnalysisScope,
    PaginationPolicy,
    ScopeType,
)
from crypto_investigator.importers.provider import ProviderRecordImporter
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.capabilities import (
    required_capabilities_complete,
    unresolved_required_errors,
)
from crypto_investigator.providers.dedup import deduplicate_records
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
    analysis_scope: AnalysisScope | None = None,
    first_hop_goal: FirstHopGoal | None = None,
    local_labels: tuple = (),
) -> dict[str, Path]:
    registry = ProviderFactory.create_registry(
        settings, refresh=refresh, cache_ttl=cache_ttl
    )
    collector = ProviderCollector(ProviderSelectionPolicy(registry, settings))
    scope = analysis_scope or AnalysisScope(
        scope_type="quick_preview",
        pagination_policy=PaginationPolicy.BOUNDED,
        max_pages=settings.pagination.max_pages,
        max_records=settings.pagination.max_records,
    )
    provider_options: dict[str, object] = {
        "unbounded": scope.pagination_policy is PaginationPolicy.TO_PROVIDER_END,
        "date_from": scope.date_from,
        "date_to": scope.date_to,
    }
    if scope.pagination_policy is PaginationPolicy.BOUNDED:
        provider_options.update(
            max_pages=scope.max_pages or settings.pagination.max_pages,
            max_records=scope.max_records or settings.pagination.max_records,
        )
    if kind == "address":
        collection = await collector.collect_address(
            chain,
            identifier,
            provider=provider,
            provider_options=provider_options,
        )
    else:
        collection = await collector.collect_transaction(
            chain,
            identifier,
            provider=provider,
            provider_options=provider_options,
        )
    provider_raw_count = sum(
        len(result.records) for result in collection.results
    )
    scoped_results = []
    for result in collection.results:
        deduplicated = deduplicate_records(result.records)
        records, excluded = apply_scope(deduplicated, scope)
        pagination = (
            replace(
                result.pagination,
                accepted_records=len(records),
                excluded_by_scope=excluded,
                deduplicated_records=len(result.records) - len(deduplicated),
            )
            if result.pagination is not None
            else None
        )
        scoped_results.append(
            replace(result, records=records, pagination=pagination)
        )
    scoped_record_count = sum(len(result.records) for result in scoped_results)
    scoped_deduplicated_records = deduplicate_records(
        record
        for result in scoped_results
        for record in result.records
    )
    deduplicated_count = (
        sum(
            result.pagination.deduplicated_records
            for result in scoped_results
            if result.pagination is not None
        )
        + scoped_record_count
        - len(scoped_deduplicated_records)
    )
    collection = replace(
        collection,
        results=tuple(scoped_results),
        records=scoped_deduplicated_records,
    )
    time_scope = build_time_scope_result(scope, collection.results)
    provider_pipeline = ProviderRecordImporter().to_domain_partial(
        collection.records, DataPipeline()
    )
    transactions = provider_pipeline.transactions
    analysis = AnalysisEngine().analyze(
        transactions, identifier if kind == "address" else None
    )
    rejected_count = len(provider_pipeline.rejected_records)
    required_complete = required_capabilities_complete(
        chain, collection.results
    )
    required_errors = unresolved_required_errors(
        chain, collection.results, collection.errors
    )
    scope_complete = (
        required_complete
        and scope.scope_type is not ScopeType.QUICK_PREVIEW
    )
    completeness = (
        "failed"
        if not transactions
        and (
            rejected_count
            or required_errors
            or any(result.missing_data for result in collection.results)
        )
        else (
            "partial"
            if rejected_count
            or required_errors
            or not scope_complete
            else "complete"
        )
    )
    provider_status_for_product = tuple(
        {
            "capability": result.capability.value,
            "final_completeness": result.completeness.value,
            "truncated": result.truncated,
        }
        for result in collection.results
    )
    product_goal = first_hop_goal or FirstHopGoal(
        required_capabilities=tuple(
            dict.fromkeys(result.capability.value for result in collection.results)
        ),
        scope_type=scope.scope_type.value,
        completeness_required="complete",
    )
    first_hop_product = (
        build_first_hop_product(
            tuple(
                {
                    "tx_hash": item.tx_hash,
                    "asset_symbol": item.asset_symbol,
                    "asset_contract": item.asset_contract,
                    "amount": str(item.amount or 0),
                    "decimals": 0,
                    "from_address": item.from_address,
                    "to_address": item.to_address,
                    "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                    "source_type": (
                        "token_transfer"
                        if item.transaction_type.value == "token_transfer"
                        else "native"
                    ),
                    "transaction_type": item.transaction_type.value,
                }
                for item in transactions
                if item.timestamp is not None
            ),
            provider_status_for_product,
            target_address=identifier,
            chain=chain.value,
            goal=product_goal,
            labels=local_labels,
        )
        if kind == "address"
        else {}
    )
    analysis = replace(
        analysis,
        metadata={
            **analysis.metadata,
            "chain": chain.value,
            "target_address": identifier if kind == "address" else None,
            "tx_hash": identifier if kind != "address" else None,
            "rejected_record_count": rejected_count,
            "completeness": completeness,
            "analysis_scope": scope.model_dump(mode="json"),
            "time_scope": time_scope.model_dump(mode="json"),
            "provider_raw_record_count": provider_raw_count,
            "normalized_record_count": len(transactions),
            "analysis_record_count": len(transactions),
            "excluded_by_scope": time_scope.excluded_by_scope,
            "deduplicated_record_count": deduplicated_count,
            "first_hop_product": first_hop_product,
            "principal_assets": (
                [first_hop_product["principal_asset"]["asset"]]
                if first_hop_product.get("principal_asset")
                else []
            ),
        },
        warnings=(
            *analysis.warnings,
            *((f"rejected_provider_records={rejected_count}",) if rejected_count else ()),
        ),
    )
    paths = AnalysisExporter().export_all(analysis, output_dir)
    if first_hop_product:
        product_paths = write_first_hop_product(first_hop_product, output_dir)
        paths["first_hop_product"] = product_paths["product"]
        paths["first_hop_chart_manifest"] = product_paths["chart_manifest"]
    paths.update(
        write_provider_outputs(
            output_dir,
            collection,
            rejected_records=provider_pipeline.rejected_records,
            analysis_completeness=completeness,
        )
    )
    return paths
