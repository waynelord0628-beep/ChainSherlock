from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_models import (
    ArtifactCandidate,
    ArtifactType,
    CancellationToken,
    Completeness,
    ExecutionStepStatus,
    StepExecutionResult,
)
from crypto_investigator.application.execution_registry import ExecutionRegistry
from crypto_investigator.cases.evidence import EvidenceManager
from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.core.export import TransactionExporter
from crypto_investigator.domain.fund_trace_engine import investigate_fund_trace
from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    SeedType,
    TraceDirection,
    TraceEdge,
    TraceRunStatus,
    TraceScope,
    TraceSeed,
)
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.export import GraphExporter
from crypto_investigator.graphs.trace_adapter import trace_result_to_graph
from crypto_investigator.importers.factory import ImporterFactory
from crypto_investigator.importers.validator import DataValidator
from crypto_investigator.investigation.feature_engine import InvestigationFeatureEngine
from crypto_investigator.normalizers.factory import NormalizerFactory
from crypto_investigator.planner.models import PlanStep, StepType
from crypto_investigator.services.case_artifact_aggregator import CaseArtifactAggregator
from crypto_investigator.application.case_report_service import CaseReportService


_STRUCTURED_SUFFIXES = {".csv", ".xls", ".xlsx"}


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def _candidate_path(context: ExecutionContext, path: Path) -> str:
    return path.relative_to(context.execution_dir).as_posix()


def _output_dir(context: ExecutionContext) -> Path:
    output = context.step_dir / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    return output


def _evidence_records(case: CaseRecord, step: PlanStep | None = None):
    selected = set(step.target_ids if step else ())
    return tuple(
        item
        for item in case.evidence
        if (not selected or item.evidence_id in selected)
        and Path(item.relative_path).suffix.casefold() in _STRUCTURED_SUFFIXES
    )


def _load_transactions(
    repository: CaseRepository,
    case: CaseRecord,
    token: CancellationToken,
):
    transactions = []
    validator = DataValidator()
    for evidence in _evidence_records(case):
        token.raise_if_cancelled()
        EvidenceManager(repository).assert_integrity(case.case_id, evidence.evidence_id)
        path = repository.workspace(case.case_id).resolve_relative(evidence.relative_path)
        batch = ImporterFactory.create(path).load(path)
        validation = validator.validate(batch.records)
        if not validation.is_valid:
            raise ValueError(
                f"Evidence contains {len(validation.issues)} validation issue(s)"
            )
        for record in validation.valid_records:
            chain = NormalizerFactory.chain_for_record(record)
            transactions.append(NormalizerFactory.create(chain).normalize(record))
    if not transactions:
        raise ValueError("No supported CSV or Excel transaction evidence is available")
    return tuple(transactions)


def _target_address(case: CaseRecord, step: PlanStep | None = None) -> str | None:
    if step and step.target_type == "address" and step.target_ids:
        return step.target_ids[0]
    known = case.metadata.get("known_addresses", [])
    if known:
        return str(known[0])
    for goal in case.goals:
        targets = goal.get("target_entities", [])
        if targets:
            return str(targets[0])
    return None


def _analysis(
    repository: CaseRepository,
    case: CaseRecord,
    token: CancellationToken,
    step: PlanStep | None = None,
    context: ExecutionContext | None = None,
):
    records = _evidence_records(case)
    if not records:
        for artifact in reversed(context.execution.artifacts if context else []):
            if artifact.artifact_type is ArtifactType.ANALYSIS_RESULT:
                path = repository.workspace(case.case_id).resolve_relative(
                    artifact.relative_path
                )
                return (), AnalysisExporter().read_analysis(path)
        raise ValueError("No verified analysis artifact is available")
    transactions = _load_transactions(repository, case, token)
    target = _target_address(case, step)
    result = AnalysisEngine().analyze(transactions, target)
    chains = sorted({item.chain.value for item in transactions})
    metadata = {
        **dict(result.metadata),
        "chain": chains[0] if len(chains) == 1 else None,
        "chains": chains,
        "completeness": "complete",
        "source": "case_evidence",
    }
    return transactions, replace(result, metadata=metadata)


class OfflineStepHandler:
    resume_supported = True
    retry_supported = False
    expected_artifacts: tuple[str, ...] = ()

    def __init__(
        self,
        repository: CaseRepository,
        step_type: StepType,
        expected_artifacts: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.supported_step_type = step_type
        self.expected_artifacts = expected_artifacts

    def validate_input(
        self, case: CaseRecord, step: PlanStep, context: ExecutionContext
    ) -> None:
        if case.case_id != context.case.case_id:
            raise ValueError("Execution case mismatch")
        if step.step_type in {
            StepType.PARSE_STRUCTURED_ATTACHMENT,
            StepType.IMPORT_TRANSACTIONS,
        } and not _evidence_records(case):
            raise ValueError("This offline step requires CSV or Excel evidence")

    def execute(
        self,
        case: CaseRecord,
        step: PlanStep,
        context: ExecutionContext,
        cancellation_token: CancellationToken,
    ) -> StepExecutionResult:
        method = getattr(self, f"_execute_{step.step_type.value}")
        return method(case, step, context, cancellation_token)

    def cancel(self, context: ExecutionContext) -> None:
        return None

    def _execute_validate_case_inputs(self, case, step, context, token):
        manager = EvidenceManager(self.repository)
        verified = []
        for evidence in case.evidence:
            token.raise_if_cancelled()
            if not manager.verify(case.case_id, evidence.evidence_id):
                raise ValueError(f"Evidence integrity failed: {evidence.evidence_id}")
            verified.append(evidence.evidence_id)
        path = _write_json(
            _output_dir(context) / "validated_case_inputs.json",
            {"case_id": case.case_id, "verified_evidence_ids": sorted(verified)},
        )
        return self._result(
            context, path, ArtifactType.OTHER, len(verified), "offline_validation"
        )

    def _execute_parse_structured_attachment(self, case, step, context, token):
        records = 0
        files = []
        for evidence in _evidence_records(case, step):
            token.raise_if_cancelled()
            EvidenceManager(self.repository).assert_integrity(
                case.case_id, evidence.evidence_id
            )
            source = self.repository.workspace(case.case_id).resolve_relative(
                evidence.relative_path
            )
            batch = ImporterFactory.create(source).load(source)
            records += len(batch.records)
            files.append(
                {
                    "evidence_id": evidence.evidence_id,
                    "record_count": len(batch.records),
                    "file_type": evidence.file_type,
                }
            )
        path = _write_json(
            _output_dir(context) / "parsed_records_summary.json",
            {"files": files, "record_count": records},
        )
        return self._result(
            context, path, ArtifactType.OTHER, records, "offline_importer"
        )

    def _execute_import_transactions(self, case, step, context, token):
        transactions, analysis = _analysis(self.repository, case, token, step)
        output = _output_dir(context)
        exports = TransactionExporter().export(
            transactions, output, Path("case_evidence")
        )
        exports.summary_json.unlink(missing_ok=True)
        analysis_path = output / "analysis.json"
        AnalysisExporter().write_json(analysis_path, analysis)
        return StepExecutionResult(
            status=ExecutionStepStatus.COMPLETED,
            records_processed=len(transactions),
            artifacts=[
                self._artifact(
                    context,
                    exports.transactions_csv,
                    ArtifactType.NORMALIZED_TRANSACTIONS,
                    "offline_data_pipeline",
                ),
                self._artifact(
                    context,
                    analysis_path,
                    ArtifactType.ANALYSIS_RESULT,
                    "offline_analysis_engine",
                ),
            ],
            safe_details={"source": "case_evidence", "records": len(transactions)},
        )

    def _execute_detect_chain(self, case, step, context, token):
        if _evidence_records(case):
            transactions = _load_transactions(self.repository, case, token)
            chains = sorted({item.chain.value for item in transactions})
            records = len(transactions)
        else:
            chains = [step.chain.value] if step.chain else []
            records = len(step.target_ids)
        path = _write_json(
            _output_dir(context) / "detected_chain.json",
            {"chains": chains, "target_count": len(step.target_ids)},
        )
        return self._result(
            context, path, ArtifactType.OTHER, records, "offline_detection"
        )

    def _execute_analyze_address(self, case, step, context, token):
        return self._execute_analysis(case, step, context, token)

    def _execute_analyze_transaction(self, case, step, context, token):
        return self._execute_analysis(case, step, context, token)

    def _execute_analysis(self, case, step, context, token):
        transactions, analysis = _analysis(self.repository, case, token, step)
        path = _output_dir(context) / "analysis.json"
        AnalysisExporter().write_json(path, analysis)
        return self._result(
            context,
            path,
            ArtifactType.ANALYSIS_RESULT,
            len(transactions),
            "offline_analysis_engine",
        )

    def _execute_trace_funds(self, case, step, context, token):
        transactions = _load_transactions(self.repository, case, token)
        target = _target_address(case, step)
        if not target or step.chain is None:
            raise ValueError("Fund tracing requires a confirmed address and chain")
        evidence_refs = tuple(
            sorted(item.evidence_id for item in case.evidence)
        ) or ("CASE-ANALYSIS",)
        edges = []
        for transaction in transactions:
            token.raise_if_cancelled()
            if (
                transaction.chain is not step.chain
                or transaction.success is False
                or not transaction.from_address
                or not transaction.to_address
                or not transaction.tx_hash
                or not transaction.asset_symbol
                or transaction.amount is None
                or transaction.amount <= 0
                or transaction.timestamp is None
            ):
                continue
            material = (
                f"{transaction.chain.value}|{transaction.tx_hash}|"
                f"{transaction.from_address}|{transaction.to_address}|"
                f"{transaction.asset_symbol}|{transaction.amount}"
            )
            edges.append(
                TraceEdge(
                    edge_id="EDGE-" + hashlib.sha256(
                        material.encode("utf-8")
                    ).hexdigest()[:20],
                    from_address=transaction.from_address,
                    to_address=transaction.to_address,
                    transaction_hash=transaction.tx_hash,
                    asset=transaction.asset_symbol,
                    amount=transaction.amount,
                    timestamp=transaction.timestamp,
                    allocation_method=AllocationMethod.DIRECT_TRANSACTION,
                    confidence=Decimal("1"),
                    evidence_refs=evidence_refs,
                )
            )
        if not edges:
            raise ValueError("No evidence-backed transfer edges are available")
        assets = tuple(step.assets) or tuple(
            sorted({edge.asset for edge in edges})
        )
        parameters = step.parameters
        scope = TraceScope(
            scope_type=str(parameters.get("scope_type", "case_evidence")),
            max_depth=int(parameters.get("max_depth", 3)),
            max_nodes=int(parameters.get("max_nodes", 100)),
            max_records=int(parameters.get("max_records") or len(edges)),
            min_material_amount=Decimal(
                str(parameters.get("min_material_amount", "0"))
            ),
            asset_filters=assets,
            direction=TraceDirection(
                str(parameters.get("direction", "bidirectional"))
            ),
        )
        result, checkpoint = investigate_fund_trace(
            run_id=f"{context.execution.execution_id}:{step.step_id}",
            seed=TraceSeed(
                SeedType.ADDRESS,
                target,
                step.chain.value,
                None,
                evidence_refs,
            ),
            scope=scope,
            available_edges=tuple(edges),
            cancelled=lambda: token.is_cancelled,
        )
        output = _output_dir(context)
        result_path = _write_json(output / "trace_result.json", result.to_dict())
        graph_paths = GraphExporter().export_all(
            trace_result_to_graph(result), output / "trace_graph"
        )
        artifacts = [
            self._artifact(
                context,
                result_path,
                ArtifactType.TRACE_RESULT,
                "offline_multihop_trace",
                completeness=(
                    Completeness.COMPLETE
                    if result.status is TraceRunStatus.COMPLETED
                    else Completeness.PARTIAL
                ),
            ),
            *[
                self._artifact(
                    context,
                    path,
                    ArtifactType.TRACE_GRAPH,
                    "offline_multihop_trace",
                    completeness=(
                        Completeness.COMPLETE
                        if result.status is TraceRunStatus.COMPLETED
                        else Completeness.PARTIAL
                    ),
                )
                for path in graph_paths.values()
            ],
        ]
        checkpoint_model = None
        if checkpoint is not None:
            checkpoint_path = _write_json(
                context.checkpoints_dir / f"{step.step_id}.json",
                checkpoint.to_dict(),
            )
            artifacts.append(
                self._artifact(
                    context,
                    checkpoint_path,
                    ArtifactType.CHECKPOINT,
                    "offline_multihop_trace",
                    completeness=Completeness.PARTIAL,
                )
            )
            from crypto_investigator.application.execution_models import (
                ExecutionCheckpoint,
            )

            checkpoint_model = ExecutionCheckpoint(
                execution_id=context.execution.execution_id,
                step_id=step.step_id,
                checkpoint_type="multihop_trace",
                state=checkpoint.to_dict(),
                completed_units=len(result.edges),
                artifact_refs=[_candidate_path(context, checkpoint_path)],
            )
        partial = result.status is not TraceRunStatus.COMPLETED
        return StepExecutionResult(
            status=(
                ExecutionStepStatus.PARTIAL
                if partial
                else ExecutionStepStatus.COMPLETED
            ),
            artifacts=artifacts,
            records_processed=len(result.edges),
            partial=partial,
            checkpoint=checkpoint_model,
            safe_details={
                "source": "case_evidence",
                "nodes": len(result.nodes),
                "edges": len(result.edges),
                "allocations": len(result.allocations),
                "patterns": len(result.patterns),
                "off_ramp_candidates": len(result.off_ramp_candidates),
            },
        )

    def _execute_build_graph(self, case, step, context, token):
        transactions, analysis = _analysis(
            self.repository, case, token, context=context
        )
        chains = {item.chain for item in transactions}
        chain_value = analysis.metadata.get("chain")
        if not chains and chain_value:
            from crypto_investigator.domain.transaction import Chain

            chains = {Chain(chain_value)}
        if len(chains) != 1:
            raise ValueError("Offline graph requires evidence from exactly one chain")
        graph = GraphBuilder().build(
            analysis,
            chain=next(iter(chains)),
            target_address=_target_address(case),
        )
        paths = GraphExporter().export_all(graph, _output_dir(context))
        type_by_name = {
            "json": ArtifactType.GRAPH_JSON,
            "graphml": ArtifactType.GRAPHML,
            "html": ArtifactType.GRAPH_HTML,
        }
        return StepExecutionResult(
            records_processed=analysis.summary.transaction_count,
            artifacts=[
                self._artifact(
                    context, path, type_by_name[name], "offline_graph_engine"
                )
                for name, path in paths.items()
            ],
        )

    def _execute_run_investigation_features(self, case, step, context, token):
        transactions, analysis = _analysis(
            self.repository, case, token, context=context
        )
        target = _target_address(case)
        if not target:
            raise ValueError("Investigation features require a confirmed target address")
        investigation = InvestigationFeatureEngine().analyze(analysis, target)
        output = _output_dir(context)
        paths = {
            "investigation": output / "investigation.json",
            "observations": output / "observations.json",
            "conclusion_facts": output / "conclusion_facts.json",
        }
        AnalysisExporter().write_json(paths["investigation"], investigation)
        AnalysisExporter().write_json(paths["observations"], investigation.observations)
        AnalysisExporter().write_json(
            paths["conclusion_facts"], investigation.conclusion_fact_items
        )
        return StepExecutionResult(
            records_processed=analysis.summary.transaction_count,
            artifacts=[
                self._artifact(
                    context,
                    paths["investigation"],
                    ArtifactType.INVESTIGATION_RESULT,
                    "offline_investigation_engine",
                ),
                self._artifact(
                    context,
                    paths["observations"],
                    ArtifactType.OBSERVATIONS,
                    "offline_investigation_engine",
                ),
                self._artifact(
                    context,
                    paths["conclusion_facts"],
                    ArtifactType.CONCLUSION_FACTS,
                    "offline_investigation_engine",
                ),
            ],
        )

    def _execute_export_evidence_manifest(self, case, step, context, token):
        token.raise_if_cancelled()
        path = _write_json(
            _output_dir(context) / "evidence_manifest.json",
            [
                {
                    "evidence_id": item.evidence_id,
                    "relative_path": item.relative_path,
                    "sha256": item.sha256,
                    "size": item.size,
                    "file_type": item.file_type,
                    "imported_at": item.imported_at.isoformat(),
                }
                for item in sorted(case.evidence, key=lambda value: value.evidence_id)
            ],
        )
        return self._result(
            context,
            path,
            ArtifactType.EVIDENCE_MANIFEST,
            len(case.evidence),
            "case_evidence_manifest",
        )

    def _execute_generate_report(self, case, step, context, token):
        token.raise_if_cancelled()
        result = CaseArtifactAggregator(self.repository).aggregate(
            case.case_id, execution_id=context.execution.execution_id
        )
        prior_failures = [
            item
            for item in context.execution.steps
            if item.step_id != step.step_id
            and item.status
            not in {ExecutionStepStatus.COMPLETED, ExecutionStepStatus.SKIPPED}
        ]
        if not prior_failures and not result.warnings and not result.limitations:
            result = result.model_copy(update={"completeness": "complete"})
        summary = CaseReportService(self.repository).generate(result, "all")
        workspace = self.repository.workspace(case.case_id)
        output = _output_dir(context)
        type_by_name = {
            "case_report.md": ArtifactType.REPORT_MARKDOWN,
            "case_report.html": ArtifactType.REPORT_HTML,
            "case_report.docx": ArtifactType.REPORT_DOCX,
            "case_report.pdf": ArtifactType.REPORT_PDF,
            "case_report_data.json": ArtifactType.OTHER,
            "case_evidence_manifest.json": ArtifactType.EVIDENCE_MANIFEST,
            "case_export_status.json": ArtifactType.OTHER,
            "case_export_errors.json": ArtifactType.OTHER,
        }
        artifacts = []
        for name, relative in sorted(summary["files"].items()):
            source = workspace.resolve_relative(relative)
            destination = output / name
            shutil.copy2(source, destination)
            artifacts.append(
                self._artifact(
                    context,
                    destination,
                    type_by_name.get(name, ArtifactType.OTHER),
                    "offline_case_report",
                    completeness=(
                        Completeness.COMPLETE
                        if summary["status"] == "complete"
                        else Completeness.PARTIAL
                    ),
                )
            )
        return StepExecutionResult(
            status=(
                ExecutionStepStatus.COMPLETED
                if summary["status"] == "complete"
                else ExecutionStepStatus.PARTIAL
            ),
            partial=summary["status"] != "complete",
            artifacts=artifacts,
            safe_details={
                "report_version": summary["report_version"],
                "export_status": summary["status"],
            },
        )

    def _result(self, context, path, artifact_type, records, source):
        return StepExecutionResult(
            records_processed=records,
            artifacts=[self._artifact(context, path, artifact_type, source)],
        )

    def _artifact(
        self,
        context,
        path,
        artifact_type,
        source,
        completeness=Completeness.COMPLETE,
    ):
        return ArtifactCandidate(
            artifact_type=artifact_type,
            relative_path=_candidate_path(context, path),
            source=source,
            completeness=completeness,
        )


def create_offline_execution_registry(
    repository: CaseRepository,
    *,
    include_analysis_handlers: bool = True,
    include_trace_handler: bool = True,
) -> ExecutionRegistry:
    registry = ExecutionRegistry()
    definitions = {
        StepType.VALIDATE_CASE_INPUTS: ("other",),
        StepType.PARSE_STRUCTURED_ATTACHMENT: ("other",),
        StepType.IMPORT_TRANSACTIONS: (
            "normalized_transactions",
            "analysis_result",
        ),
        StepType.DETECT_CHAIN: ("other",),
        StepType.BUILD_GRAPH: ("graph_json", "graphml", "graph_html"),
        StepType.RUN_INVESTIGATION_FEATURES: (
            "investigation_result",
            "observations",
            "conclusion_facts",
        ),
        StepType.EXPORT_EVIDENCE_MANIFEST: ("evidence_manifest",),
        StepType.GENERATE_REPORT: ("report_markdown", "report_html", "report_docx"),
    }
    if include_trace_handler:
        definitions[StepType.TRACE_FUNDS] = ("trace_result", "trace_graph")
    if include_analysis_handlers:
        definitions.update(
            {
                StepType.ANALYZE_ADDRESS: ("analysis_result",),
                StepType.ANALYZE_TRANSACTION: ("analysis_result",),
            }
        )
    for step_type, artifacts in definitions.items():
        registry.register(OfflineStepHandler(repository, step_type, artifacts))
    return registry
