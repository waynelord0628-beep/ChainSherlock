from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Mapping

from crypto_investigator.investigation.behavior import (
    build_behavior,
    build_conclusion_facts,
    build_observations,
)
from crypto_investigator.investigation.clustering import analyze_relationships
from crypto_investigator.investigation.counterparty import analyze_counterparty_concentration
from crypto_investigator.investigation.exchange import detect_services
from crypto_investigator.investigation.direction import reconcile_directions
from crypto_investigator.investigation.activity import analyze_activity
from crypto_investigator.investigation.distribution import analyze_fifo_distribution
from crypto_investigator.investigation.evidence import build_evidence
from crypto_investigator.investigation.conclusion_facts import structured_conclusion_facts
from crypto_investigator.investigation.funding import (
    analyze_funding,
    analyze_initial_funding,
)
from crypto_investigator.investigation.investigation_result import (
    InvestigationResult,
    InvestigationSettings,
    InvestigationMetadata,
    InvestigationWarning,
    LabelMatch,
    OperationStageAnalysis,
    LabelRecord,
    RelationshipResult,
)
from crypto_investigator.investigation.patterns import (
    analyze_distribution,
    analyze_transfer_patterns,
)
from crypto_investigator.investigation.timeline import (
    detect_dormant_periods,
    detect_operation_stages,
)


class InvestigationFeatureEngine:
    def __init__(self, settings: InvestigationSettings | None = None):
        self.settings = settings or InvestigationSettings()

    def analyze(
        self,
        analysis,
        target_address: str,
        *,
        labels: tuple[LabelRecord, ...] = (),
        related_analyses: Mapping[str, object] | None = None,
    ) -> InvestigationResult:
        edges = analysis.flow.edges
        funding = analyze_funding(edges, target_address)
        dormant = detect_dormant_periods(edges, self.settings.dormant_days)
        stages = detect_operation_stages(edges, funding, dormant)
        concentration = analyze_counterparty_concentration(analysis.counterparties)
        distribution = analyze_distribution(edges, target_address)
        chain = (
            str((getattr(analysis, "metadata", {}) or {}).get("chain"))
            if (getattr(analysis, "metadata", {}) or {}).get("chain")
            else None
        )
        distribution_analysis = analyze_fifo_distribution(
            edges, target_address, chain
        )
        activity = analyze_activity(edges, self.settings.timezone)
        patterns = analyze_transfer_patterns(edges, target_address, self.settings)
        services = detect_services(analysis.counterparties, labels)
        counterparty_addresses = {
            item.address.casefold() for item in analysis.counterparties
        }
        label_matches = tuple(
            LabelMatch(
                address=item.address,
                chain=item.chain,
                label=item.label,
                category=item.category,
                source=item.source,
                confidence=item.confidence,
                reference=item.reference,
            )
            for item in labels
            if item.address.casefold() in counterparty_addresses
        )
        relationships = (
            analyze_relationships(related_analyses)
            if related_analyses
            else RelationshipResult()
        )
        behavior = build_behavior(
            analysis, funding, stages, dormant, concentration, distribution, patterns
        )
        observations = build_observations(funding, dormant, patterns)
        conclusion = build_conclusion_facts(
            funding, dormant, concentration, patterns
        )
        timestamps = sorted(edge.timestamp for edge in edges if edge.timestamp)
        source_from = timestamps[0] if timestamps else None
        source_to = timestamps[-1] if timestamps else None
        analysis_metadata = getattr(analysis, "metadata", {}) or {}
        completeness = str(analysis_metadata.get("completeness", "complete"))
        deterministic_time = source_to or datetime(1970, 1, 1, tzinfo=UTC)
        settings_snapshot = {
            "dormant_days": self.settings.dormant_days,
            "batch_window_minutes": self.settings.batch_window_minutes,
            "batch_minimum_count": self.settings.batch_minimum_count,
            "fixed_amount_minimum_count": self.settings.fixed_amount_minimum_count,
            "funding_window_days": self.settings.funding_window_days,
            "minimum_funding_transactions": self.settings.minimum_funding_transactions,
            "minimum_funding_amount": self.settings.minimum_funding_amount,
            "dominant_source_min_share": self.settings.dominant_source_min_share,
            "transition_persistence_days": self.settings.transition_persistence_days,
            "timezone": self.settings.timezone,
        }
        reconciliation = reconcile_directions(analysis, target_address)
        warnings = ()
        if completeness != "complete":
            warnings = (
                InvestigationWarning(
                    "partial_source_data",
                    "Source analysis is partial; confidence is reduced.",
                    "low",
                ),
            )
        metadata = {
            "engine_version": "6.5",
            "deterministic": True,
            "target_address": target_address,
            "analysis_completeness": completeness,
            "settings": settings_snapshot,
        }
        result = InvestigationResult(
            funding=funding,
            stages=stages,
            dormant_periods=dormant,
            counterparty_concentration=concentration,
            services=services,
            distribution=distribution,
            transfer_patterns=patterns,
            relationships=relationships,
            behavior=behavior,
            observations=observations,
            conclusion_facts=conclusion,
            metadata=metadata,
            direction_reconciliation=reconciliation,
            structured_metadata=InvestigationMetadata(
                target_address=target_address,
                chain=str(analysis_metadata.get("chain")) if analysis_metadata.get("chain") else None,
                generated_at=deterministic_time,
                source_transaction_count=len(edges),
                analysis_completeness=completeness,
                graph_completeness=str(analysis_metadata.get("graph_completeness", "not_provided")),
                source_date_from=source_from,
                source_date_to=source_to,
                assets=tuple(sorted({edge.asset for edge in edges})),
                settings_snapshot=settings_snapshot,
            ),
            warnings=warnings,
            evidence_refs=build_evidence(edges, funding, deterministic_time),
            label_matches=label_matches,
            distribution_analysis=distribution_analysis,
            activity=activity,
            stage_analysis=OperationStageAnalysis(stages),
            initial_funding=analyze_initial_funding(
                edges, target_address, (item.address for item in labels)
            ),
        )
        return replace(
            result,
            conclusion_fact_items=structured_conclusion_facts(result),
        )

    def analyze_public_mapping(
        self,
        value: Mapping[str, object],
        target_address: str,
        *,
        labels: tuple[LabelRecord, ...] = (),
    ) -> InvestigationResult:
        flow = value.get("flow", {})
        edges = tuple(
            SimpleNamespace(
                source=item["source"],
                target=item["target"],
                direction=item.get("direction"),
                weight=Decimal(str(item["weight"])),
                asset=item["asset"],
                timestamp=(
                    __import__("datetime").datetime.fromisoformat(item["timestamp"])
                    if item.get("timestamp")
                    else None
                ),
                tx_hash=item["tx_hash"],
            )
            for item in flow.get("edges", ())
        )
        counterparties = tuple(
            SimpleNamespace(
                **{
                    **item,
                    "interaction_count": int(item["interaction_count"]),
                    "incoming_count": int(item["incoming_count"]),
                    "outgoing_count": int(item["outgoing_count"]),
                }
            )
            for item in value.get("counterparties", ())
        )
        analysis = SimpleNamespace(
            flow=SimpleNamespace(edges=edges),
            counterparties=counterparties,
            statistics=SimpleNamespace(
                transaction_frequency=value.get("statistics", {}).get(
                    "transaction_frequency", 0
                )
            ),
            metadata=value.get("metadata", {}),
        )
        return self.analyze(analysis, target_address, labels=labels)

    @staticmethod
    def annotate_graph(graph, investigation: InvestigationResult):
        funding = {item.address.casefold() for item in investigation.funding.sources}
        current_stage = (
            investigation.stages[-1].stage if investigation.stages else None
        )
        nodes = tuple(
            replace(
                node,
                metadata={
                    **node.metadata,
                    "funding_source": node.address.casefold() in funding,
                    "operation_stage": current_stage if node.is_target else None,
                },
            )
            for node in graph.nodes
        )
        return replace(graph, nodes=nodes)
