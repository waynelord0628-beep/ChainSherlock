from decimal import Decimal

from crypto_investigator.investigation.investigation_result import (
    BehaviorSummary,
    ConclusionFacts,
    Observation,
)


def build_behavior(analysis, funding, stages, dormant, concentration, distribution, patterns):
    frequency = Decimal(str(analysis.statistics.transaction_frequency))
    return BehaviorSummary(
        funding_pattern="concentrated" if funding.concentration >= Decimal("0.6") else "diversified",
        distribution_pattern="batch" if patterns.batch_outgoing_count else ("forwarding" if distribution.matched_transfer_count else "retained"),
        frequency=frequency,
        counterparty_pattern="concentrated" if concentration.top10_ratio >= Decimal("0.6") else "distributed",
        activity_pattern="intermittent" if dormant else "continuous",
        operation_stages=tuple(stage.stage for stage in stages),
        dormant=bool(dormant),
        recovery=any(item.reactivated for item in dormant),
    )


def build_observations(funding, dormant, patterns) -> tuple[Observation, ...]:
    observations = [
        Observation(
            "funding_source_changed",
            item.occurred_at,
            {"previous_source": item.previous_source, "current_source": item.current_source},
            (
                f"主要供款來源由 {item.previous_source} 變更為 "
                f"{item.current_source}。"
            ),
            {"transition_count": 1},
            ("monthly_dominant_source_changed",),
            ("IF0",),
        )
        for item in funding.transitions
    ]
    observations.extend(
        Observation(
            "dormant_reactivation",
            item.ended_at,
            {"dormant_days": item.dormant_days, "reactivated": item.reactivated},
            f"目前樣本顯示連續 {item.dormant_days} 天沒有交易，之後出現交易。",
            {"dormant_days": item.dormant_days},
            ("transaction_gap_exceeds_threshold",),
            ("IF0",),
        )
        for item in dormant
    )
    if patterns.batch_outgoing_count:
        observations.append(
            Observation(
                "batch_distribution",
                None,
                {"batch_count": patterns.batch_outgoing_count},
                f"共有 {patterns.batch_outgoing_count} 個流出時間窗符合目前 batch rule。",
                {"batch_window_count": patterns.batch_outgoing_count},
                ("batch_minimum_count_reached",),
                ("IF0",),
            )
        )
    return tuple(observations)


def build_conclusion_facts(funding, dormant, concentration, patterns):
    longest = max((item.dormant_days for item in dormant), default=0)
    return ConclusionFacts(
        funding_source_changed=bool(funding.transitions),
        dormant_days=longest,
        main_counterparty_ratio=concentration.top10_ratio,
        top_provider_changed=bool(funding.transitions),
        batch_distribution=bool(patterns.batch_outgoing_count),
        funding_concentration=funding.concentration,
        reactivated=any(item.reactivated for item in dormant),
    )
