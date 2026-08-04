from crypto_investigator.investigation.investigation_result import ConclusionFact


def structured_conclusion_facts(result, *, graph_truncated=False, provider_truncated=False):
    confidence = "low" if result.metadata.get("analysis_completeness") != "complete" else "high"
    provider_truncated = provider_truncated or confidence == "low"
    evidence = ("IF0",) if result.evidence_refs else ()
    limitation = (
        ("partial provider data may change this fact",)
        if confidence == "low" else ()
    )
    dominant_by_asset = {
        asset: addresses[0]
        for asset, addresses in result.funding.top_sources_by_asset.items()
        if addresses
    }
    values = (
        ("dominant_funder_exists", bool(result.funding.sources), None),
        ("dominant_funder_address", dominant_by_asset, "address_by_asset"),
        (
            "dominant_funder_share_by_asset",
            result.funding.concentration_by_asset,
            "ratio_by_asset",
        ),
        ("funding_source_changed", bool(result.funding.transitions), None),
        ("funding_transition_count", len(result.funding.transitions), "count"),
        ("dormant_period_detected", bool(result.dormant_periods), None),
        ("longest_dormant_days", max((item.dormant_days for item in result.dormant_periods), default=0), "days"),
        ("reactivation_detected", any(item.reactivated for item in result.dormant_periods), None),
        ("batch_incoming_detected", bool(result.transfer_patterns.batch_incoming_count), None),
        ("batch_outgoing_detected", bool(result.transfer_patterns.batch_outgoing_count), None),
        ("fixed_amount_pattern_detected", any(result.transfer_patterns.fixed_amounts.values()), None),
        ("rapid_pass_through_detected", bool(result.distribution.matched_transfer_count and result.distribution.median_holding_seconds is not None and result.distribution.median_holding_seconds <= 3600), None),
        ("service_candidate_count", len(result.services), "count"),
        ("graph_truncated", graph_truncated, None),
        ("provider_truncated", provider_truncated, None),
        ("analysis_partial", result.metadata.get("analysis_completeness") != "complete", None),
        ("unknown_direction_count", result.direction_reconciliation.unclassified_direction_count if result.direction_reconciliation else 0, "count"),
    )
    return tuple(
        ConclusionFact(
            code, value, unit, confidence, ("deterministic_rule",),
            evidence, limitation,
        )
        for code, value, unit in values
    )
