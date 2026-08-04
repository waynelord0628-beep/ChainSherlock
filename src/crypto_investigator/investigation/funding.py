from collections import defaultdict
from decimal import Decimal

from crypto_investigator.investigation.investigation_result import (
    FundingAnalysis,
    FundingPeriod,
    FundingSource,
    FundingTransition,
    InitialFundingCandidate,
)
from crypto_investigator.investigation.statistics import ratio
from crypto_investigator.investigation.statistics import median


def analyze_funding(edges, target_address: str | None) -> FundingAnalysis:
    incoming = [
        edge for edge in edges
        if target_address and edge.target.casefold() == target_address.casefold()
    ]
    grouped = defaultdict(list)
    for edge in incoming:
        grouped[edge.source].append(edge)
    ranked = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].casefold()))
    sources = []
    totals_by_asset = defaultdict(Decimal)
    for edge in incoming:
        totals_by_asset[edge.asset] += edge.weight
    for rank, (address, records) in enumerate(ranked, 1):
        amounts = defaultdict(Decimal)
        values = defaultdict(list)
        timestamps = sorted(edge.timestamp for edge in records if edge.timestamp)
        for edge in records:
            amounts[edge.asset] += edge.weight
            values[edge.asset].append(edge.weight)
        sources.append(
            FundingSource(
                address=address,
                transaction_count=len(records),
                transaction_ratio=ratio(len(records), len(incoming)),
                amounts_by_asset=dict(sorted(amounts.items())),
                first_funding=timestamps[0] if timestamps else None,
                last_funding=timestamps[-1] if timestamps else None,
                rank=rank,
                assets=tuple(sorted(amounts)),
                incoming_count=len(records),
                share_by_asset={
                    asset: ratio(amount, totals_by_asset[asset])
                    for asset, amount in sorted(amounts.items())
                },
                active_days=len({item.date() for item in timestamps}),
                average_amount_by_asset={
                    asset: ratio(amount, len(values[asset]))
                    for asset, amount in sorted(amounts.items())
                },
                median_amount_by_asset={
                    asset: median(values[asset]) or Decimal("0")
                    for asset in sorted(values)
                },
                maximum_amount_by_asset={
                    asset: max(values[asset]) for asset in sorted(values)
                },
                evidence_transaction_hashes=tuple(sorted(edge.tx_hash for edge in records)),
            )
        )
    monthly = defaultdict(list)
    for edge in incoming:
        if edge.timestamp:
            monthly[edge.timestamp.strftime("%Y-%m")].append(edge)
    periods = []
    for period, records in sorted(monthly.items()):
        counts = defaultdict(int)
        for edge in records:
            counts[edge.source] += 1
        main = sorted(counts, key=lambda address: (-counts[address], address.casefold()))[0]
        periods.append(
            FundingPeriod(period, main, len(counts), len(records), ratio(counts[main], len(records)))
        )
    transitions = []
    for previous, current in zip(periods, periods[1:]):
        if previous.main_source and current.main_source and previous.main_source != current.main_source:
            first = min(
                edge.timestamp for edge in monthly[current.period]
                if edge.timestamp and edge.source == current.main_source
            )
            transitions.append(
                FundingTransition(first, previous.main_source, current.main_source)
            )
    concentration = sources[0].transaction_ratio if sources else Decimal("0")
    by_asset = {}
    top_by_asset = {}
    first_by_asset = {}
    latest_by_asset = {}
    for asset in sorted(totals_by_asset):
        candidates = [item for item in sources if asset in item.amounts_by_asset]
        candidates.sort(
            key=lambda item: (-item.amounts_by_asset[asset], item.address.casefold())
        )
        by_asset[asset] = (
            candidates[0].share_by_asset[asset] if candidates else Decimal("0")
        )
        top_by_asset[asset] = tuple(item.address for item in candidates)
        asset_edges = sorted(
            (edge for edge in incoming if edge.asset == asset and edge.timestamp),
            key=lambda edge: (edge.timestamp, edge.tx_hash),
        )
        if asset_edges:
            first_by_asset[asset] = asset_edges[0].source
            latest_by_asset[asset] = asset_edges[-1].source
    return FundingAnalysis(
        tuple(sources),
        tuple(periods),
        tuple(transitions),
        concentration,
        by_asset,
        top_by_asset,
        first_by_asset,
        latest_by_asset,
    )


def analyze_initial_funding(edges, target_address: str, labeled_addresses=()):
    target = target_address.casefold()
    labels = {item.casefold() for item in labeled_addresses}
    first = {}
    for edge in sorted(
        (item for item in edges if item.timestamp),
        key=lambda item: (item.timestamp, item.tx_hash),
    ):
        if edge.target.casefold() == target and edge.asset not in first:
            first[edge.asset] = InitialFundingCandidate(
                edge.asset,
                edge.weight,
                edge.source,
                edge.timestamp,
                edge.tx_hash,
                edge.weight <= Decimal("0.000001"),
                edge.source.casefold() in labels,
                "high",
            )
    return tuple(first[asset] for asset in sorted(first))
