from decimal import Decimal

from crypto_investigator.investigation.investigation_result import ConcentrationMetrics
from crypto_investigator.investigation.statistics import entropy, gini, herfindahl, ratio


def analyze_counterparty_concentration(counterparties) -> ConcentrationMetrics:
    counts = sorted(
        (item.interaction_count for item in counterparties), reverse=True
    )
    total = sum(counts)
    hhi = herfindahl(counts)
    normalized = (
        (hhi - ratio(1, len(counts))) / (Decimal("1") - ratio(1, len(counts)))
        if len(counts) > 1 else hhi
    )
    return ConcentrationMetrics(
        top10_ratio=ratio(sum(counts[:10]), total),
        top20_ratio=ratio(sum(counts[:20]), total),
        top50_ratio=ratio(sum(counts[:50]), total),
        herfindahl_index=hhi,
        gini=gini(counts),
        entropy=entropy(counts),
        top1_ratio=ratio(sum(counts[:1]), total),
        top3_ratio=ratio(sum(counts[:3]), total),
        top5_ratio=ratio(sum(counts[:5]), total),
        normalized_herfindahl_index=normalized,
        effective_counterparty_count=(
            Decimal("1") / hhi if hhi else Decimal("0")
        ),
    )
