from collections import defaultdict

from crypto_investigator.domain.scope import (
    AnalysisScope,
    ScopeType,
    TimeScopeResult,
    in_scope,
)
from crypto_investigator.providers.capabilities import (
    required_capabilities_complete,
)


def apply_scope(records, scope: AnalysisScope):
    accepted = tuple(
        record for record in records if in_scope(record.timestamp, scope)
    )
    return accepted, len(records) - len(accepted)


def build_time_scope_result(
    scope: AnalysisScope,
    provider_results,
) -> TimeScopeResult:
    results = tuple(provider_results)
    scoped = []
    excluded = 0
    first_by_asset = {}
    last_by_asset = {}
    first_by_capability = {}
    last_by_capability = {}
    for result in results:
        records, removed = apply_scope(result.records, scope)
        scoped.extend(records)
        excluded += removed
        timestamps = sorted(
            item.timestamp for item in records if item.timestamp is not None
        )
        if timestamps:
            capability = result.capability.value
            first_by_capability[capability] = min(
                first_by_capability.get(capability, timestamps[0]),
                timestamps[0],
            )
            last_by_capability[capability] = max(
                last_by_capability.get(capability, timestamps[-1]),
                timestamps[-1],
            )
        assets = defaultdict(list)
        for record in records:
            if record.timestamp is not None:
                assets[record.asset_symbol or "native"].append(record.timestamp)
        for asset, values in assets.items():
            first_by_asset[asset] = min(
                first_by_asset.get(asset, min(values)), min(values)
            )
            last_by_asset[asset] = max(
                last_by_asset.get(asset, max(values)), max(values)
            )
    timestamps = sorted(
        item.timestamp for item in scoped if item.timestamp is not None
    )
    full_complete = bool(results) and required_capabilities_complete(
        results[0].chain, results
    )
    if scope.scope_type != ScopeType.FULL_HISTORY:
        full_complete = False
    return TimeScopeResult(
        scope_type=scope.scope_type,
        requested_date_from=scope.date_from,
        requested_date_to=scope.date_to,
        timezone=scope.timezone,
        overall_first_seen=timestamps[0] if timestamps else None,
        overall_last_seen=timestamps[-1] if timestamps else None,
        first_seen_by_asset=first_by_asset,
        last_seen_by_asset=last_by_asset,
        first_seen_by_capability=first_by_capability,
        last_seen_by_capability=last_by_capability,
        full_history_complete=full_complete,
        excluded_by_scope=excluded,
    )
