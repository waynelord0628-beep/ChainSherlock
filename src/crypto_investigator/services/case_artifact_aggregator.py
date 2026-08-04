from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from crypto_investigator.application import ArtifactType, ExecutionStatus
from crypto_investigator.cases import AuditLog, CaseRepository
from crypto_investigator.cases.evidence import sha256_file
from crypto_investigator.cases.results import (
    AuditSummary,
    CandidateType,
    CaseFact,
    CaseInterpretation,
    CaseObservation,
    CaseResult,
    EvidenceIndexEntry,
    RecommendedFollowUp,
    UnresolvedQuestion,
)
from crypto_investigator.services.artifact_service import ArtifactService
from crypto_investigator.services.execution_state_service import ExecutionStateService


class CaseArtifactAggregator:
    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository
        self.state = ExecutionStateService(repository)

    def aggregate(self, case_id: str) -> CaseResult:
        case = self.repository.load(case_id)
        workspace = self.repository.workspace(case_id)
        warnings: list[str] = []
        limitations: list[str] = []
        evidence_index = [
            EvidenceIndexEntry(
                evidence_id=item.evidence_id,
                evidence_type="source_evidence",
                description=item.description or item.original_filename,
                relative_path=item.relative_path,
                sha256=item.sha256,
                size=item.size,
                source="case_evidence",
                created_at=item.imported_at,
                integrity_status="verified",
            )
            for item in case.evidence
        ]
        executions = []
        payloads: list[tuple[Any, dict[str, Any]]] = []
        artifact_service = ArtifactService(workspace)
        for summary in case.executions:
            try:
                execution = self.state.load(summary["execution_id"], case_id)
            except Exception:
                warnings.append(f"Missing execution: {summary.get('execution_id', 'unknown')}")
                continue
            executions.append(execution)
            for artifact in execution.artifacts:
                integrity = artifact_service.verify(artifact)
                evidence_index.append(
                    EvidenceIndexEntry(
                        evidence_id=artifact.artifact_id,
                        evidence_type=artifact.artifact_type.value,
                        description=artifact.source,
                        relative_path=artifact.relative_path,
                        sha256=artifact.sha256,
                        size=artifact.size,
                        source=artifact.source,
                        created_at=artifact.created_at,
                        integrity_status="verified" if integrity else "hash_mismatch",
                    )
                )
                if not integrity:
                    warnings.append(f"Artifact integrity failed: {artifact.artifact_id}")
                    continue
                if artifact.completeness.value == "partial":
                    limitations.append(f"Partial artifact: {artifact.artifact_id}")
                if artifact.artifact_type in {
                    ArtifactType.ANALYSIS_RESULT,
                    ArtifactType.INVESTIGATION_RESULT,
                    ArtifactType.NARRATIVE_RESULT,
                    ArtifactType.PROVIDER_STATUS,
                    ArtifactType.PROVIDER_ERRORS,
                    ArtifactType.REJECTED_RECORDS,
                }:
                    try:
                        value = json.loads(
                            workspace.resolve_relative(artifact.relative_path).read_text(
                                encoding="utf-8"
                            )
                        )
                        if isinstance(value, dict):
                            payloads.append((artifact, value))
                    except (OSError, ValueError):
                        warnings.append(f"Unsupported artifact schema: {artifact.artifact_id}")

        facts: list[CaseFact] = []
        observations: list[CaseObservation] = []
        candidates: list[CaseInterpretation] = []
        address_results: list[dict[str, Any]] = []
        transaction_results: list[dict[str, Any]] = []
        chains: set[str] = set()
        assets: set[str] = set()
        addresses: set[str] = set()
        transactions: set[str] = set()
        for artifact, payload in payloads:
            chain = payload.get("chain") or payload.get("metadata", {}).get("chain")
            if chain:
                chains.add(str(chain))
            summary = payload.get("summary", {})
            for asset in summary.get("assets", payload.get("assets", [])):
                assets.add(str(asset))
            target = payload.get("target_address") or payload.get("metadata", {}).get(
                "target_address"
            )
            if artifact.artifact_type is ArtifactType.ANALYSIS_RESULT:
                item = {
                    "address": target,
                    "chain": chain,
                    "transaction_count": summary.get("transaction_count", 0),
                    "asset_summaries": summary.get("assets", []),
                    "completeness": payload.get("metadata", {}).get(
                        "completeness", "unknown"
                    ),
                    "artifact_refs": [artifact.artifact_id],
                    "warnings": payload.get("warnings", []),
                }
                if target:
                    addresses.add(str(target))
                    address_results.append(item)
                elif payload.get("tx_hash"):
                    transactions.add(str(payload["tx_hash"]))
                    transaction_results.append(
                        {**item, "tx_hash": payload["tx_hash"]}
                    )
            if artifact.artifact_type is ArtifactType.INVESTIGATION_RESULT:
                for index, raw in enumerate(payload.get("conclusion_fact_items", []), 1):
                    facts.append(
                        CaseFact(
                            fact_id=f"fact_{artifact.artifact_id}_{index}",
                            category=str(raw.get("fact_code", "investigation")),
                            statement=f"{raw.get('fact_code', 'fact')} = {raw.get('value')}",
                            structured_value=raw.get("value"),
                            source_type="deterministic_investigation",
                            source_refs=[artifact.artifact_id],
                            evidence_ids=list(raw.get("evidence_refs", [])),
                            confidence=str(raw.get("confidence", "medium")),
                            limitations=list(raw.get("limitations", [])),
                        )
                    )
                for index, raw in enumerate(payload.get("observations", []), 1):
                    observations.append(
                        CaseObservation(
                            observation_id=f"observation_{artifact.artifact_id}_{index}",
                            source_address=target,
                            category=str(raw.get("code", "investigation")),
                            factual_statement=str(
                                raw.get("factual_statement", raw.get("code", "Observation"))
                            ),
                            metrics=dict(raw.get("metrics", raw.get("facts", {}))),
                            confidence=str(raw.get("confidence", "medium")),
                            evidence_refs=list(raw.get("evidence_refs", [])),
                            limitations=list(raw.get("limitations", [])),
                            source_artifact=artifact.artifact_id,
                        )
                    )
                for index, raw in enumerate(payload.get("services", []), 1):
                    service_type = str(raw.get("service_type", "unknown"))
                    candidate_type = (
                        CandidateType.EXCHANGE
                        if "exchange" in service_type
                        else CandidateType.SERVICE
                    )
                    candidates.append(
                        CaseInterpretation(
                            interpretation_id=f"candidate_{artifact.artifact_id}_{index}",
                            title=f"{service_type} candidate",
                            statement=f"{raw.get('address', 'Address')} is a possible {service_type}.",
                            candidate_type=candidate_type,
                            evidence_refs=list(raw.get("evidence_refs", [])),
                            confidence="low",
                            alternative_explanations=[
                                "The observed behavior may have another operational explanation."
                            ],
                            limitations=["Candidate interpretation is not a confirmed identity."],
                        )
                    )

        questions = []
        for goal in case.goals:
            questions.append(
                UnresolvedQuestion(
                    question_id=f"question_{goal.get('goal_id', len(questions)+1)}",
                    question=f"Has goal '{goal.get('title', goal.get('goal_type'))}' been fully resolved?",
                    related_goals=[str(goal.get("goal_id", ""))],
                    reason_unresolved="Requires analyst review of available evidence.",
                    required_data=["reviewed evidence"],
                )
            )
        for index, warning in enumerate(warnings, 1):
            questions.append(
                UnresolvedQuestion(
                    question_id=f"question_warning_{index}",
                    question="Can the missing or invalid data be obtained and verified?",
                    reason_unresolved=warning,
                    required_data=["valid artifact or source data"],
                )
            )
        recommendations = [
            RecommendedFollowUp(
                recommendation_id=f"followup_{item.question_id}",
                title="Resolve outstanding evidence question",
                description=item.question,
                related_goal=item.related_goals[0] if item.related_goals else None,
                evidence_refs=item.evidence_refs,
                reason=item.reason_unresolved,
                expected_answer="Verified data or an explicit unavailable finding.",
                possible_cost=None,
                supported_by_current_system=False,
                external_permission_required=True,
            )
            for item in questions
        ]
        audit_entries = list(AuditLog(workspace).entries())
        supporting_paths = [
            ("audit_log", "audit_log", workspace.audit_file),
            *[
                (
                    f"execution_log_{execution.execution_id}",
                    "execution_log",
                    self.state.execution_dir(case_id, execution.execution_id)
                    / "logs"
                    / "execution.jsonl",
                )
                for execution in executions
            ],
        ]
        supporting_paths.extend(
            (
                f"report_{path.parent.name}_{path.stem}",
                "case_report_artifact",
                path,
            )
            for path in sorted(workspace.path.glob("reports/v*/case_report*"))
            if path.is_file()
        )
        for evidence_id, evidence_type, path in supporting_paths:
            if not path.is_file():
                continue
            evidence_index.append(
                EvidenceIndexEntry(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    description=path.name,
                    relative_path=path.relative_to(workspace.path).as_posix(),
                    sha256=sha256_file(path),
                    size=path.stat().st_size,
                    source="case_workspace",
                    integrity_status="verified",
                )
            )
        counts = Counter(item.action for item in audit_entries)
        audit = AuditSummary(
            entry_count=len(audit_entries),
            action_counts=dict(sorted(counts.items())),
            first_event_at=audit_entries[0].timestamp if audit_entries else None,
            last_event_at=audit_entries[-1].timestamp if audit_entries else None,
            chain_integrity=AuditLog(workspace).verify(),
        )
        partial = bool(warnings or limitations) or any(
            item.status is not ExecutionStatus.COMPLETED for item in executions
        )
        return CaseResult(
            case_id=case.case_id,
            case_number=case.metadata.get("case_number"),
            title=case.title,
            case_status=case.status.value,
            execution_ids=[item.execution_id for item in executions],
            plan_ids=sorted({item.plan_id for item in executions}),
            investigation_goals=list(case.goals),
            analysis_scope={"execution_count": len(executions), "artifact_count": len(evidence_index)},
            chains=sorted(chains),
            assets=sorted(assets),
            known_addresses=sorted(addresses),
            known_transactions=sorted(transactions),
            evidence_summary={"count": len(evidence_index)},
            execution_summary=dict(case.execution_summary),
            address_results=address_results,
            transaction_results=transaction_results,
            confirmed_facts=facts,
            deterministic_observations=observations,
            candidate_interpretations=candidates,
            unresolved_questions=questions,
            recommended_follow_ups=recommendations,
            limitations=sorted(set(limitations)),
            evidence_index=evidence_index,
            audit_summary=audit,
            warnings=warnings,
            completeness="partial" if partial else "complete",
        )
