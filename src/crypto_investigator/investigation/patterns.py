from collections import Counter, defaultdict, deque
from datetime import timedelta
from decimal import Decimal

from crypto_investigator.investigation.investigation_result import (
    DistributionMetrics,
    TransferPattern,
)
from crypto_investigator.investigation.statistics import median, ratio


def analyze_distribution(edges, target_address: str | None) -> DistributionMetrics:
    if not target_address:
        return DistributionMetrics(0, None, None)
    ordered = sorted((edge for edge in edges if edge.timestamp), key=lambda edge: (edge.timestamp, edge.tx_hash))
    incoming = defaultdict(deque)
    durations = []
    for edge in ordered:
        if edge.target.casefold() == target_address.casefold():
            incoming[edge.asset].append(edge)
        elif edge.source.casefold() == target_address.casefold() and incoming[edge.asset]:
            source = incoming[edge.asset].popleft()
            durations.append(Decimal(str((edge.timestamp - source.timestamp).total_seconds())))
    if not durations:
        return DistributionMetrics(0, None, None)
    return DistributionMetrics(
        len(durations),
        sum(durations, Decimal("0")) / len(durations),
        median(durations),
    )


def analyze_transfer_patterns(edges, target_address: str | None, settings) -> TransferPattern:
    amount_counts = defaultdict(Counter)
    suffix_counts = Counter()
    integer_count = 0
    buckets_in = Counter()
    buckets_out = Counter()
    for edge in edges:
        amount_counts[edge.asset][edge.weight] += 1
        integer_count += int(edge.weight == edge.weight.to_integral_value())
        suffix_counts[str(edge.weight).split(".")[-1][-2:]] += 1
        if edge.timestamp and target_address:
            bucket = edge.timestamp.replace(
                minute=(edge.timestamp.minute // settings.batch_window_minutes) * settings.batch_window_minutes,
                second=0,
                microsecond=0,
            )
            if edge.source.casefold() == target_address.casefold():
                buckets_out[bucket] += 1
            if edge.target.casefold() == target_address.casefold():
                buckets_in[bucket] += 1
    fixed = {
        asset: tuple(
            amount for amount, count in sorted(values.items())
            if count >= settings.fixed_amount_minimum_count
        )
        for asset, values in sorted(amount_counts.items())
    }
    return TransferPattern(
        fixed_amounts=fixed,
        integer_amount_ratio=ratio(integer_count, len(edges)),
        amount_suffix_counts=dict(sorted(suffix_counts.items())),
        batch_outgoing_count=sum(count >= settings.batch_minimum_count for count in buckets_out.values()),
        batch_incoming_count=sum(count >= settings.batch_minimum_count for count in buckets_in.values()),
    )
