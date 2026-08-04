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


def detect_operation_stages(edges, funding, dormant_periods) -> tuple[OperationStage, ...]:
    ordered = sorted((edge for edge in edges if edge.timestamp), key=lambda edge: (edge.timestamp, edge.tx_hash))
    if not ordered:
        return ()
    count = len(ordered)
    split = max(1, count // 5)
    stages = [
        OperationStage("startup", ordered[0].timestamp, ordered[split - 1].timestamp, split, ratio(split, max(1, (ordered[split - 1].timestamp - ordered[0].timestamp).days + 1)), funding.concentration),
    ]
    middle = ordered[split:]
    if middle:
        stage_name = "diversification" if funding.concentration < Decimal("0.5") else "dominant"
        stages.append(OperationStage(stage_name, middle[0].timestamp, middle[-1].timestamp, len(middle), ratio(len(middle), max(1, (middle[-1].timestamp - middle[0].timestamp).days + 1)), funding.concentration))
    for period in dormant_periods:
        stages.append(OperationStage("dormant", period.started_at, period.ended_at, 0, Decimal("0"), funding.concentration))
        if period.reactivated:
            stages.append(OperationStage("recovery", period.ended_at, ordered[-1].timestamp, len([edge for edge in ordered if edge.timestamp >= period.ended_at]), period.post_recovery_daily_frequency, funding.concentration))
    return tuple(sorted(stages, key=lambda item: (item.started_at, item.stage)))
