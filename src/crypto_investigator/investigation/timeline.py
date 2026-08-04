from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from crypto_investigator.investigation.investigation_result import (
    DormantPeriod,
    OperationStage,
)
from crypto_investigator.investigation.statistics import ratio


def detect_dormant_periods(edges, dormant_days: int) -> tuple[DormantPeriod, ...]:
    ordered = sorted((edge for edge in edges if edge.timestamp), key=lambda edge: (edge.timestamp, edge.tx_hash))
    results = []
    for before, after in zip(ordered, ordered[1:]):
        days = (after.timestamp - before.timestamp).days
        if days < dormant_days:
            continue
        recovery = [edge for edge in ordered if after.timestamp <= edge.timestamp <= after.timestamp + timedelta(days=30)]
        by_asset = defaultdict(list)
        for edge in recovery:
            by_asset[edge.asset].append(edge.weight)
        averages = {
            asset: sum(values, Decimal("0")) / len(values)
            for asset, values in sorted(by_asset.items())
        }
        frequency = ratio(len(recovery), 30)
        prior = [edge for edge in ordered if before.timestamp - timedelta(days=30) <= edge.timestamp <= before.timestamp]
        prior_frequency = ratio(len(prior), 30)
        results.append(
            DormantPeriod(
                before.timestamp,
                after.timestamp,
                days,
                True,
                averages,
                frequency,
                abs(frequency - prior_frequency) >= Decimal("0.1"),
            )
        )
    return tuple(results)


def detect_operation_stages(
    edges, funding, dormant_periods, target_address: str | None = None
) -> tuple[OperationStage, ...]:
    ordered = sorted((edge for edge in edges if edge.timestamp), key=lambda edge: (edge.timestamp, edge.tx_hash))
    if not ordered:
        return ()
    count = len(ordered)
    split = max(1, count // 5)
    assets = tuple(sorted({edge.asset for edge in ordered}))
    funders = tuple(
        dict.fromkeys(
            addresses[0]
            for _, addresses in sorted(funding.top_sources_by_asset.items())
            if addresses
        )
    )
    outgoing_counts = defaultdict(int)
    if target_address:
        target = target_address.casefold()
        for edge in ordered:
            if edge.source.casefold() == target:
                outgoing_counts[edge.target] += 1
    destinations = tuple(
        address
        for address, _ in sorted(
            outgoing_counts.items(), key=lambda item: (-item[1], item[0])
        )[:3]
    )
    stages = [
        OperationStage(
            "startup", ordered[0].timestamp, ordered[split - 1].timestamp,
            split,
            ratio(split, max(1, (ordered[split - 1].timestamp - ordered[0].timestamp).days + 1)),
            funding.concentration, assets, funders, destinations,
            ("first_sample_window",), ("IF0",), "medium",
        ),
    ]
    middle = ordered[split:]
    if middle:
        stage_name = "diversification" if funding.concentration < Decimal("0.5") else "dominant"
        stages.append(OperationStage(
            stage_name, middle[0].timestamp, middle[-1].timestamp, len(middle),
            ratio(len(middle), max(1, (middle[-1].timestamp - middle[0].timestamp).days + 1)),
            funding.concentration, assets, funders, destinations,
            ("funding_concentration_threshold",), ("IF0",), "medium",
        ))
    for period in dormant_periods:
        stages.append(OperationStage(
            "dormant", period.started_at, period.ended_at, 0, Decimal("0"),
            funding.concentration, assets, funders, destinations,
            ("transaction_gap_exceeds_threshold",), ("IF0",), "medium",
        ))
        if period.reactivated:
            stages.append(OperationStage(
                "recovery", period.ended_at, ordered[-1].timestamp,
                len([edge for edge in ordered if edge.timestamp >= period.ended_at]),
                period.post_recovery_daily_frequency, funding.concentration,
                assets, funders, destinations, ("activity_after_dormancy",),
                ("IF0",), "medium",
            ))
    return tuple(sorted(stages, key=lambda item: (item.started_at, item.stage)))
