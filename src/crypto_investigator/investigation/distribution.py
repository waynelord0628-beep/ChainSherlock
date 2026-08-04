from collections import defaultdict, deque
from decimal import Decimal

from crypto_investigator.investigation.investigation_result import (
    DistributionAnalysis,
    HoldingTimeStatistics,
    PassThroughEvent,
)
from crypto_investigator.investigation.statistics import median, ratio
from crypto_investigator.investigation.patterns import analyze_distribution


def analyze_fifo_distribution(edges, target_address: str, chain: str | None):
    if chain and chain.casefold() in {"bitcoin", "btc"}:
        return DistributionAnalysis("utxo_required", False, {}, ())
    queues = defaultdict(deque)
    totals_in = defaultdict(Decimal)
    totals_out = defaultdict(Decimal)
    unmatched_out = defaultdict(Decimal)
    durations = defaultdict(list)
    events = []
    ordered = sorted(
        (edge for edge in edges if edge.timestamp),
        key=lambda edge: (edge.timestamp, edge.tx_hash),
    )
    target = target_address.casefold()
    for edge in ordered:
        if edge.target.casefold() == target:
            queues[edge.asset].append([edge, edge.weight])
            totals_in[edge.asset] += edge.weight
        elif edge.source.casefold() == target:
            totals_out[edge.asset] += edge.weight
            remaining = edge.weight
            while remaining > 0 and queues[edge.asset]:
                incoming, available = queues[edge.asset][0]
                matched = min(remaining, available)
                elapsed = Decimal(
                    str((edge.timestamp - incoming.timestamp).total_seconds())
                )
                durations[edge.asset].append(elapsed)
                events.append(
                    PassThroughEvent(
                        edge.asset,
                        incoming.tx_hash,
                        (edge.tx_hash,),
                        incoming.timestamp,
                        edge.timestamp,
                        elapsed,
                        incoming.weight,
                        matched,
                        "fifo_approximation",
                        (incoming.tx_hash, edge.tx_hash),
                    )
                )
                remaining -= matched
                available -= matched
                if available == 0:
                    queues[edge.asset].popleft()
                else:
                    queues[edge.asset][0][1] = available
            unmatched_out[edge.asset] += remaining
    stats = {}
    for asset in sorted(set(totals_in) | set(totals_out)):
        values = durations[asset]
        unmatched_in = sum((item[1] for item in queues[asset]), Decimal("0"))
        matched_amount = totals_out[asset] - unmatched_out[asset]
        stats[asset] = HoldingTimeStatistics(
            asset,
            matched_amount,
            matched_amount,
            unmatched_in,
            unmatched_out[asset],
            sum(values, Decimal("0")) / len(values) if values else None,
            median(values),
            min(values) if values else None,
            max(values) if values else None,
            ratio(sum(value <= 300 for value in values), len(values)),
            ratio(sum(value <= 3600 for value in values), len(values)),
            ratio(sum(value <= 86400 for value in values), len(values)),
            ratio(sum(value <= 604800 for value in values), len(values)),
            len(values),
        )
    return DistributionAnalysis(
        "fifo_approximation",
        True,
        stats,
        tuple(events),
    )

__all__ = ["analyze_distribution", "analyze_fifo_distribution"]
