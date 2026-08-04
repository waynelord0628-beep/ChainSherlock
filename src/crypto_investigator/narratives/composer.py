from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from crypto_investigator.investigation.investigation_result import InvestigationResult
from crypto_investigator.narratives.models import NarrativeInput
from crypto_investigator.narratives.sections import DEFAULT_SECTIONS


def _primitive(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {key: _primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_primitive(item) for item in value)
    return value


class NarrativeInputBuilder:
    """Build the only data contract that may cross the AI provider boundary."""

    def build(
        self,
        result: InvestigationResult,
        *,
        language: str = "zh-TW",
        tone: str = "professional",
        requested_sections: tuple[str, ...] = DEFAULT_SECTIONS,
    ) -> NarrativeInput:
        metadata = result.structured_metadata
        analysis_period = {
            "from": _primitive(metadata.source_date_from) if metadata else None,
            "to": _primitive(metadata.source_date_to) if metadata else None,
        }
        limitations = tuple(warning.message for warning in result.warnings)
        provider_limits = tuple(
            warning.message
            for warning in result.warnings
            if "provider" in warning.code.lower()
        )
        assets = metadata.assets if metadata else ()
        asset_summaries = tuple({"asset": asset} for asset in assets)
        patterns = result.transfer_pattern_analysis
        pattern_items = ()
        if patterns:
            pattern_items = tuple(
                {"pattern_type": "batch", **_primitive(item)} for item in patterns.batches
            ) + tuple(
                {"pattern_type": "fixed_amount", **_primitive(item)}
                for item in patterns.fixed_amounts
            ) + tuple(
                {"pattern_type": "round_amount", **_primitive(item)}
                for item in patterns.round_amounts
            )
        holding = ()
        if result.distribution_analysis:
            holding = tuple(
                {"asset": asset, **_primitive(stats)}
                for asset, stats in sorted(
                    result.distribution_analysis.statistics_by_asset.items()
                )
            )
        roles = result.counterparty_analysis.roles if result.counterparty_analysis else ()
        fact_items = result.conclusion_fact_items or tuple(
            {"fact_code": key, "value": _primitive(value)}
            for key, value in asdict(result.conclusion_facts).items()
        )
        return NarrativeInput(
            report_metadata={
                "investigation_version": metadata.investigation_version if metadata else "6.5",
                "transaction_count": metadata.source_transaction_count if metadata else 0,
            },
            target_address=metadata.target_address if metadata else str(result.metadata.get("target_address", "")),
            chain=metadata.chain if metadata else result.metadata.get("chain"),
            analysis_period=analysis_period,
            completeness=metadata.analysis_completeness if metadata else str(result.metadata.get("completeness", "unknown")),
            provider_limits=provider_limits,
            asset_summaries=asset_summaries,
            direction_reconciliation=_primitive(result.direction_reconciliation) if result.direction_reconciliation else {},
            funding_sources=tuple(_primitive(item) for item in result.funding.sources),
            outgoing_destinations=self._outgoing(result),
            funding_transitions=tuple(_primitive(item) for item in result.funding.transitions),
            operation_stages=tuple(_primitive(item) for item in result.stages),
            dormancy=tuple(_primitive(item) for item in result.dormant_periods),
            holding_time=holding,
            transfer_patterns=pattern_items,
            concentration_metrics=_primitive(result.counterparty_concentration),
            counterparty_roles=tuple(_primitive(item) for item in roles),
            label_matches=tuple(_primitive(item) for item in result.label_matches),
            observations=tuple(_primitive(item) for item in result.observations),
            conclusion_facts=tuple(_primitive(item) for item in fact_items),
            limitations=limitations,
            evidence_index=tuple(_primitive(item) for item in result.evidence_refs),
            language=language,
            tone=tone,
            requested_sections=requested_sections,
        )

    @staticmethod
    def _outgoing(result: InvestigationResult) -> tuple[dict[str, Any], ...]:
        if not result.counterparty_analysis:
            return ()
        rows = []
        for name, ranking in sorted(result.counterparty_analysis.rankings.items()):
            if "out" in name.lower():
                rows.extend({"ranking": name, **_primitive(item)} for item in ranking)
        return tuple(rows)
