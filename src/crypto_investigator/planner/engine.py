from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import PurePosixPath
from typing import Iterable

from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.config import Settings
from crypto_investigator.detection.identifier import IdentifierKind, detect_identifier
from crypto_investigator.planner.errors import NoExecutableClueError
from crypto_investigator.planner.goals import GoalType, InvestigationGoal
from crypto_investigator.planner.models import (
    InvestigationPlan,
    PlanStep,
    PlanWarning,
    PlannerType,
    StepStatus,
    StepType,
    WarningKind,
    plan_now,
)
from crypto_investigator.planner.rules import STRUCTURED_SUFFIXES, capability_requirements
from crypto_investigator.planner.steps import make_step
from crypto_investigator.planner.validation import validate_plan
from crypto_investigator.providers.models import ProviderDescriptor


class DeterministicPlanner:
    def __init__(
        self,
        settings: Settings,
        *,
        provider_descriptors: Iterable[ProviderDescriptor] = (),
        ai_enabled: bool = False,
    ) -> None:
        self.settings = settings
        self.descriptors = tuple(provider_descriptors)
        self.ai_enabled = ai_enabled

    def create_plan(
        self,
        case: CaseRecord,
        goals: Iterable[InvestigationGoal],
        *,
        generated_at: datetime | None = None,
    ) -> InvestigationPlan:
        ordered_goals = sorted(
            goals,
            key=lambda item: (-int(item.priority), item.goal_type.value, item.goal_id),
        )
        steps: list[PlanStep] = []

        def add(step_type: StepType, title: str, reason: str, **kwargs) -> PlanStep:
            existing = next(
                (
                    item
                    for item in steps
                    if item.step_type is step_type
                    and item.target_ids == list(kwargs.get("target_ids", []))
                ),
                None,
            )
            if existing is not None:
                return existing
            step = make_step(
                step_type,
                order=len(steps) + 1,
                title=title,
                reason=reason,
                occurrence=sum(item.step_type is step_type for item in steps),
                **kwargs,
            )
            steps.append(step)
            return step

        validate_inputs = add(
            StepType.VALIDATE_CASE_INPUTS,
            "Validate case inputs",
            "All plans begin with deterministic input validation.",
            expected_outputs=["validated_case_inputs"],
        )
        import_steps: list[PlanStep] = []
        for evidence in sorted(case.evidence, key=lambda item: item.evidence_id):
            if PurePosixPath(evidence.relative_path).suffix.lower() not in STRUCTURED_SUFFIXES:
                continue
            parsed = add(
                StepType.PARSE_STRUCTURED_ATTACHMENT,
                "Parse structured attachment",
                "Structured evidence must be parsed before transaction import.",
                target_ids=[evidence.evidence_id],
                target_type="evidence",
                prerequisites=[validate_inputs.step_id],
                evidence_basis=[evidence.evidence_id],
                expected_outputs=["parsed_records"],
            )
            imported = add(
                StepType.IMPORT_TRANSACTIONS,
                "Import transactions",
                "Parsed records enter the existing Data Pipeline.",
                target_ids=[evidence.evidence_id],
                target_type="evidence",
                prerequisites=[parsed.step_id],
                evidence_basis=[evidence.evidence_id],
                expected_outputs=["domain_transactions"],
            )
            import_steps.append(imported)

        detected = []
        target_assets = sorted(
            {asset for goal in ordered_goals for asset in goal.target_assets}
        )
        date_ranges = [
            goal.target_date_range
            for goal in ordered_goals
            if goal.target_date_range is not None
        ]
        date_from = min(
            (item.date_from for item in date_ranges if item.date_from is not None),
            default=None,
        )
        date_to = max(
            (item.date_to for item in date_ranges if item.date_to is not None),
            default=None,
        )
        target_values = sorted(
            {value for goal in ordered_goals for value in goal.target_entities}
        )
        for value in target_values:
            try:
                detected.append(detect_identifier(value))
            except Exception:
                continue

        analysis_steps: list[PlanStep] = []
        requirements = []
        for identifier in detected:
            chain_step = add(
                StepType.DETECT_CHAIN,
                "Detect chain",
                "The target chain must be known before provider selection.",
                target_ids=[identifier.value],
                target_type=identifier.kind.value,
                chain=identifier.chain,
                prerequisites=[validate_inputs.step_id],
                expected_outputs=["detected_chain"],
            )
            if identifier.kind is IdentifierKind.ADDRESS:
                address_requirements = (
                    ()
                    if import_steps
                    else capability_requirements(identifier.chain, self.descriptors)
                )
                requirements.extend(address_requirements)
                selected_provider = next(
                    (
                        item.provider
                        for item in address_requirements
                        if item.capability == "address_transactions" and item.available
                    ),
                    None,
                )
                step = add(
                    StepType.ANALYZE_ADDRESS,
                    "Analyze address",
                    (
                        "Address analysis uses imported structured evidence."
                        if import_steps
                        else "Address analysis is required by the selected goals."
                    ),
                    target_ids=[identifier.value],
                    target_type="address",
                    chain=identifier.chain,
                    assets=target_assets,
                    date_from=date_from,
                    date_to=date_to,
                    provider=selected_provider,
                    prerequisites=[
                        chain_step.step_id,
                        *[item.step_id for item in import_steps],
                    ],
                    parameters={
                        "max_pages": self.settings.pagination.max_pages,
                        "max_records": self.settings.pagination.max_records,
                        "cache": self.settings.cache.enabled,
                        "refresh": False,
                        "data_source": (
                            "case_evidence" if import_steps else "provider"
                        ),
                    },
                    expected_outputs=["analysis_result"],
                    estimated_records=self.settings.pagination.max_records,
                    estimated_cost=None,
                )
            else:
                step = add(
                    StepType.ANALYZE_TRANSACTION,
                    "Analyze transaction",
                    "A transaction hash requires transaction-level analysis.",
                    target_ids=[identifier.value],
                    target_type="transaction",
                    chain=identifier.chain,
                    assets=target_assets,
                    date_from=date_from,
                    date_to=date_to,
                    prerequisites=[chain_step.step_id],
                    expected_outputs=["analysis_result"],
                )
            analysis_steps.append(step)

        if not analysis_steps and not import_steps:
            raise NoExecutableClueError("No executable address, transaction, or structured evidence")

        warnings: list[PlanWarning] = [
            PlanWarning(
                code="cost_unknown",
                message="No authoritative provider price is configured; cost remains unknown.",
                kind=WarningKind.COST,
            )
        ]
        for requirement in requirements:
            if requirement.available is False:
                warnings.append(
                    PlanWarning(
                        code="provider_capability_unavailable",
                        message=(
                            f"No configured provider metadata supports "
                            f"{requirement.chain.value}:{requirement.capability}"
                        ),
                        kind=WarningKind.CAPABILITY,
                    )
                )
        required_provider_names = {
            item.provider for item in requirements if item.provider is not None
        }
        for descriptor in sorted(self.descriptors, key=lambda item: item.name):
            if descriptor.name in required_provider_names and descriptor.requires_api_key:
                warnings.append(
                    PlanWarning(
                        code="provider_credentials_required",
                        message=f"Provider {descriptor.name} may require configured credentials.",
                        kind=WarningKind.PROVIDER,
                    )
                )
        prerequisites = [item.step_id for item in (*analysis_steps, *import_steps)]

        goal_types = {goal.goal_type for goal in ordered_goals}
        compare = None
        if GoalType.COMPARE_KNOWN_ADDRESSES in goal_types or len(
            [item for item in detected if item.kind is IdentifierKind.ADDRESS]
        ) > 1:
            compare = add(
                StepType.COMPARE_KNOWN_ADDRESSES,
                "Compare known addresses",
                "Multiple known addresses require deterministic relationship comparison.",
                target_ids=[
                    item.value for item in detected if item.kind is IdentifierKind.ADDRESS
                ],
                target_type="address",
                prerequisites=[item.step_id for item in analysis_steps],
                expected_outputs=["address_comparison"],
            )

        if GoalType.VERIFY_VICTIM_PAYMENT in goal_types:
            match = add(
                StepType.MATCH_VICTIM_TRANSACTIONS,
                "Match victim transactions",
                "Victim payment verification requires amount, time, address, and hash matching.",
                prerequisites=prerequisites,
                expected_outputs=["victim_transaction_matches"],
            )
            prerequisites.append(match.step_id)

        graph = investigation = manifest = None
        feature_goals = goal_types - {GoalType.CUSTOM}
        if feature_goals:
            graph = add(
                StepType.BUILD_GRAPH,
                "Build flow graph",
                "Selected goals require graph-ready flow relationships.",
                prerequisites=prerequisites,
                expected_outputs=["graph_result"],
            )
            investigation = add(
                StepType.RUN_INVESTIGATION_FEATURES,
                "Run investigation features",
                "Selected goals require deterministic investigation features.",
                prerequisites=prerequisites,
                expected_outputs=["investigation_result"],
            )

        if GoalType.IDENTIFY_EXCHANGE_EXPOSURE in goal_types:
            labels = add(
                StepType.APPLY_LOCAL_LABELS,
                "Apply local labels",
                "Exchange exposure uses local and static labels only.",
                prerequisites=prerequisites,
                expected_outputs=["local_label_matches"],
            )
            add(
                StepType.UNSUPPORTED_RECOMMENDED_STEP,
                "Commercial intelligence lookup",
                "Commercial API enrichment is outside the approved scope.",
                prerequisites=[labels.step_id],
                enabled=False,
                optional=True,
                status=StepStatus.SKIPPED,
                can_cancel=False,
                warnings=[
                    PlanWarning(
                        code="commercial_api_unsupported",
                        message="Commercial intelligence API is not available.",
                        kind=WarningKind.UNSUPPORTED,
                    )
                ],
            )

        if GoalType.GENERATE_INVESTIGATION_REPORT in goal_types:
            if graph is None or investigation is None:
                raise NoExecutableClueError("Report goal requires analyzable inputs")
            manifest = add(
                StepType.EXPORT_EVIDENCE_MANIFEST,
                "Export evidence manifest",
                "Case reports require an evidence manifest.",
                prerequisites=prerequisites,
                expected_outputs=["evidence_manifest"],
            )
            report_dependencies = [investigation.step_id, graph.step_id, manifest.step_id]
            if self.ai_enabled:
                add(
                    StepType.GENERATE_NARRATIVE,
                    "Generate optional narrative",
                    "AI narrative is optional and always requires explicit confirmation.",
                    prerequisites=[investigation.step_id],
                    expected_outputs=["narrative_result"],
                    optional=True,
                    requires_confirmation=True,
                )
            add(
                StepType.GENERATE_REPORT,
                "Generate investigation report",
                "The selected goal requests a report.",
                prerequisites=report_dependencies,
                expected_outputs=["report_document"],
            )

        settings_snapshot = {
            "max_pages": self.settings.pagination.max_pages,
            "max_records": self.settings.pagination.max_records,
            "cache": self.settings.cache.enabled,
            "ai_enabled": self.ai_enabled,
            "providers": {
                chain: {
                    "primary": getattr(self.settings.providers, chain).primary,
                    "fallback": list(getattr(self.settings.providers, chain).fallback),
                }
                for chain in ("ethereum", "tron", "bitcoin")
            },
        }
        fingerprint = {
            "case_id": case.case_id,
            "goals": [item.model_dump(mode="json") for item in ordered_goals],
            "steps": [item.model_dump(mode="json") for item in steps],
            "provider_requirements": [
                item.model_dump(mode="json") for item in requirements
            ],
            "warnings": [item.model_dump(mode="json") for item in warnings],
            "settings": settings_snapshot,
        }
        plan_id = "plan_" + hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        plan = InvestigationPlan(
            plan_id=plan_id,
            case_id=case.case_id,
            generated_at=generated_at or plan_now(),
            planner_type=PlannerType.DETERMINISTIC,
            goals=ordered_goals,
            steps=steps,
            prerequisites=[validate_inputs.step_id],
            estimated_scope={
                "targets": len(detected),
                "structured_attachments": len(import_steps),
                "steps": len(steps),
            },
            provider_requirements=list(
                {
                    (item.chain, item.capability, item.provider): item
                    for item in requirements
                }.values()
            ),
            possible_costs=None,
            warnings=warnings,
            settings_snapshot=settings_snapshot,
        )
        return validate_plan(plan)
