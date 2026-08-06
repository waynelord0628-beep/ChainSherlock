from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, replace
from datetime import datetime
from decimal import Decimal

from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_models import (
    ArtifactCandidate,
    ArtifactType,
    CancellationToken,
    Completeness,
    ExecutionStepStatus,
    ExecutionWarning,
    StepExecutionResult,
)
from crypto_investigator.application.offline_handlers import (
    OfflineStepHandler,
    _candidate_path,
    _evidence_records,
    create_offline_execution_registry,
)
from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.config import Settings, load_config
from crypto_investigator.domain.scope import AnalysisScope
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
from crypto_investigator.graphs.export import GraphExporter
from crypto_investigator.graphs.trace_adapter import trace_result_to_graph
from crypto_investigator.planner.models import PlanStep, StepType
from crypto_investigator.providers.service import analyze_provider_identifier
from crypto_investigator.providers.collector import ProviderCollector
from crypto_investigator.providers.factory import ProviderFactory
from crypto_investigator.providers.multihop import (
    ProviderCollectionCheckpoint,
    ProviderCursorState,
    collect_multihop_edges,
)
from crypto_investigator.providers.selection import ProviderSelectionPolicy


ProviderRunner = Callable[..., Awaitable[dict[str, object]]]


class ProviderAnalysisStepHandler:
    resume_supported = True
    retry_supported = False
    expected_artifacts = (
        "analysis_result",
        "provider_status",
        "provider_errors",
        "rejected_records",
    )

    def __init__(
        self,
        repository: CaseRepository,
        step_type: StepType,
        settings: Settings,
        runner: ProviderRunner = analyze_provider_identifier,
    ) -> None:
        self.repository = repository
        self.supported_step_type = step_type
        self.settings = settings
        self.runner = runner
        self.offline = OfflineStepHandler(
            repository, step_type, ("analysis_result",)
        )

    def validate_input(
        self, case: CaseRecord, step: PlanStep, context: ExecutionContext
    ) -> None:
        if _evidence_records(case):
            self.offline.validate_input(case, step, context)
            return
        if not step.target_ids:
            raise ValueError("Provider analysis requires a confirmed target")
        if step.chain is None:
            raise ValueError("Provider analysis requires a detected chain")

    def execute(
        self,
        case: CaseRecord,
        step: PlanStep,
        context: ExecutionContext,
        cancellation_token: CancellationToken,
    ) -> StepExecutionResult:
        if _evidence_records(case):
            return self.offline.execute(
                case, step, context, cancellation_token
            )
        cancellation_token.raise_if_cancelled()
        output = context.step_dir / "artifacts"
        output.mkdir(parents=True, exist_ok=True)
        kind = "address" if step.step_type is StepType.ANALYZE_ADDRESS else "transaction"
        paths = asyncio.run(
            self.runner(
                identifier=step.target_ids[0],
                chain=step.chain,
                kind=kind,
                settings=self.settings,
                output_dir=output,
                provider=None,
                refresh=bool(step.parameters.get("refresh", False)),
                cache_ttl=None,
                analysis_scope=AnalysisScope.model_validate(
                    step.parameters.get("analysis_scope")
                    or step.analysis_scope.model_dump(mode="json")
                ),
            )
        )
        cancellation_token.raise_if_cancelled()
        status_payload = self._json(paths["provider_status"])
        error_payload = self._json(paths["provider_errors"])
        rejected_payload = self._json(paths["rejected_records"])
        for name, payload in (
            ("provider_status", status_payload),
            ("provider_errors", error_payload),
            ("rejected_records", rejected_payload),
        ):
            paths[name].write_text(
                json.dumps(
                    redact_sensitive(payload),
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        error_payload = redact_sensitive(error_payload)
        analysis = self._json(paths["analysis"])
        completeness = str(
            analysis.get("metadata", {}).get("completeness", "complete")
        )
        partial = completeness != "complete"
        warnings = [
            ExecutionWarning(
                code=str(item.get("error_type", "provider_error")),
                message=str(
                    item.get(
                        "safe_message",
                        item.get("message", "Provider request was incomplete"),
                    )
                ),
                step_id=step.step_id,
            )
            for item in error_payload
            if isinstance(item, dict)
        ]
        type_by_name = {
            "analysis": ArtifactType.ANALYSIS_RESULT,
            "provider_status": ArtifactType.PROVIDER_STATUS,
            "provider_errors": ArtifactType.PROVIDER_ERRORS,
            "rejected_records": ArtifactType.REJECTED_RECORDS,
            "first_hop_product": ArtifactType.FIRST_HOP_PRODUCT,
            "first_hop_chart_manifest": ArtifactType.FIRST_HOP_CHART_MANIFEST,
        }
        candidates = [
            ArtifactCandidate(
                artifact_type=artifact_type,
                relative_path=_candidate_path(context, paths[name]),
                source=f"provider_{step.chain.value}",
                completeness=(
                    Completeness.PARTIAL if partial else Completeness.COMPLETE
                ),
                metadata={
                    "chain": step.chain.value,
                    "kind": kind,
                    "provider_count": len(
                        {
                            item.get("provider")
                            for item in status_payload
                            if isinstance(item, dict) and item.get("provider")
                        }
                    ),
                },
            )
            for name, artifact_type in type_by_name.items()
            if name in paths
        ]
        return StepExecutionResult(
            status=(
                ExecutionStepStatus.PARTIAL
                if partial
                else ExecutionStepStatus.COMPLETED
            ),
            partial=partial,
            records_processed=int(
                analysis.get("metadata", {}).get("transaction_count", 0)
            ),
            artifacts=candidates,
            warnings=warnings,
            safe_details={
                "chain": step.chain.value,
                "source": "public_provider",
                "completeness": completeness,
                "provider_results": len(status_payload),
                "provider_errors": len(error_payload),
            },
        )

    def cancel(self, context: ExecutionContext) -> None:
        return None

    @staticmethod
    def _json(path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))


class ProviderTraceStepHandler:
    supported_step_type = StepType.TRACE_FUNDS
    resume_supported = True
    retry_supported = False
    expected_artifacts = ("trace_result", "trace_graph")

    def __init__(self, repository: CaseRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def validate_input(self, case, step, context) -> None:
        if _evidence_records(case):
            return
        if not step.target_ids or step.chain is None:
            raise ValueError("Provider fund tracing requires an address and chain")

    def execute(self, case, step, context, cancellation_token):
        if _evidence_records(case):
            return OfflineStepHandler(
                self.repository,
                StepType.TRACE_FUNDS,
                ("trace_result", "trace_graph"),
            ).execute(case, step, context, cancellation_token)
        registry = ProviderFactory.create_registry(self.settings)
        collector = ProviderCollector(
            ProviderSelectionPolicy(registry, self.settings)
        )
        provider_checkpoint, previous_edges = self._resume_state(context, step)

        async def fetch(address, start_cursors, completed_capabilities):
            return await collector.collect_address(
                step.chain,
                address,
                provider=step.provider,
                provider_options={
                    "max_pages": self.settings.pagination.max_pages,
                    "max_records": self.settings.pagination.max_records,
                    "start_cursors": dict(start_cursors),
                    "completed_capabilities": tuple(completed_capabilities),
                },
            )

        parameters = step.parameters
        scope = TraceScope(
            scope_type=str(parameters.get("scope_type", "bounded_multihop")),
            max_depth=int(parameters.get("max_depth", 3)),
            max_nodes=int(parameters.get("max_nodes", 100)),
            max_records=int(
                parameters.get("max_records")
                or self.settings.pagination.max_records
            ),
            min_material_amount=Decimal(
                str(parameters.get("min_material_amount", "0"))
            ),
            asset_filters=tuple(step.assets),
            direction=TraceDirection(
                str(parameters.get("direction", "bidirectional"))
            ),
        )
        seed = TraceSeed(
            SeedType.ADDRESS,
            step.target_ids[0],
            step.chain.value,
            None,
            ("CONFIRMED-PLAN-TARGET",),
        )
        collected = asyncio.run(
            collect_multihop_edges(
                seed=seed,
                scope=scope,
                fetch_address=fetch,
                max_address_queries=scope.max_nodes,
                cancelled=lambda: cancellation_token.is_cancelled,
                checkpoint=provider_checkpoint,
                previous_edges=previous_edges,
            )
        )
        traced, _ = investigate_fund_trace(
            run_id=f"{context.execution.execution_id}:{step.step_id}",
            seed=seed,
            scope=scope,
            available_edges=collected.edges,
            cancelled=lambda: cancellation_token.is_cancelled,
            manual_stop_addresses=tuple(
                str(item)
                for item in parameters.get("manual_stop_addresses", ())
            ),
        )
        if collected.status is not TraceRunStatus.COMPLETED:
            traced = replace(
                traced,
                status=collected.status,
                limitations=tuple(
                    dict.fromkeys(
                        (*traced.limitations, *collected.limitations)
                    )
                ),
            )
        output = context.step_dir / "artifacts"
        output.mkdir(parents=True, exist_ok=True)
        result_path = output / "trace_result.json"
        result_path.write_text(
            json.dumps(traced.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        graph_paths = GraphExporter().export_all(
            trace_result_to_graph(traced), output / "trace_graph"
        )
        partial = traced.status is not TraceRunStatus.COMPLETED
        candidates = [
            ArtifactCandidate(
                artifact_type=ArtifactType.TRACE_RESULT,
                relative_path=_candidate_path(context, result_path),
                source=f"provider_{step.chain.value}_multihop",
                completeness=(
                    Completeness.PARTIAL if partial else Completeness.COMPLETE
                ),
            ),
            *[
                ArtifactCandidate(
                    artifact_type=ArtifactType.TRACE_GRAPH,
                    relative_path=_candidate_path(context, path),
                    source=f"provider_{step.chain.value}_multihop",
                    completeness=(
                        Completeness.PARTIAL
                        if partial
                        else Completeness.COMPLETE
                    ),
                )
                for path in graph_paths.values()
            ],
        ]
        checkpoint_model = None
        if collected.checkpoint is not None:
            from crypto_investigator.application.execution_models import (
                ExecutionCheckpoint,
            )

            state = {
                "provider_checkpoint": asdict(collected.checkpoint),
                "edges": [edge.to_dict() for edge in collected.edges],
            }
            checkpoint_path = context.checkpoints_dir / f"{step.step_id}.json"
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            candidates.append(
                ArtifactCandidate(
                    artifact_type=ArtifactType.CHECKPOINT,
                    relative_path=_candidate_path(context, checkpoint_path),
                    source=f"provider_{step.chain.value}_multihop",
                    completeness=Completeness.PARTIAL,
                )
            )
            checkpoint_model = ExecutionCheckpoint(
                execution_id=context.execution.execution_id,
                step_id=step.step_id,
                checkpoint_type="provider_multihop_trace",
                state=state,
                completed_units=len(collected.edges),
                artifact_refs=[_candidate_path(context, checkpoint_path)],
            )
        return StepExecutionResult(
            status=(
                ExecutionStepStatus.PARTIAL
                if partial
                else ExecutionStepStatus.COMPLETED
            ),
            artifacts=candidates,
            records_processed=len(collected.edges),
            partial=partial,
            checkpoint=checkpoint_model,
            warnings=[
                ExecutionWarning(
                    code="provider_trace_incomplete",
                    message=message,
                    step_id=step.step_id,
                )
                for message in collected.limitations
            ],
            safe_details={
                "nodes": len(traced.nodes),
                "edges": len(traced.edges),
                "provider_pages": collected.provider_page_count,
                "address_queries": collected.address_query_count,
            },
        )

    def cancel(self, context) -> None:
        return None

    @staticmethod
    def _resume_state(context, step):
        step_state = next(
            (
                item
                for item in context.execution.steps
                if item.step_id == step.step_id
            ),
            None,
        )
        if step_state is None or step_state.checkpoint is None:
            return None, ()
        state = step_state.checkpoint.state
        raw = state.get("provider_checkpoint")
        if not isinstance(raw, dict):
            return None, ()
        checkpoint = ProviderCollectionCheckpoint(
            frontier=tuple(tuple(item) for item in raw.get("frontier", ())),
            visited_states=tuple(raw.get("visited_states", ())),
            cursor_states=tuple(
                ProviderCursorState(**item)
                for item in raw.get("cursor_states", ())
            ),
            completed_edge_ids=tuple(raw.get("completed_edge_ids", ())),
            checkpoint_version=int(raw.get("checkpoint_version", 1)),
        )
        edges = tuple(
            TraceEdge(
                edge_id=item["edge_id"],
                from_address=item["from_address"],
                to_address=item["to_address"],
                transaction_hash=item["transaction_hash"],
                asset=item["asset"],
                amount=Decimal(item["amount"]),
                timestamp=datetime.fromisoformat(item["timestamp"]),
                allocation_method=AllocationMethod(item["allocation_method"]),
                confidence=Decimal(item["confidence"]),
                evidence_refs=tuple(item["evidence_refs"]),
            )
            for item in state.get("edges", ())
        )
        return checkpoint, edges


def create_desktop_execution_registry(
    repository: CaseRepository,
    *,
    settings: Settings | None = None,
    provider_runner: ProviderRunner = analyze_provider_identifier,
):
    configured = settings or load_config()
    registry = create_offline_execution_registry(
        repository,
        include_analysis_handlers=False,
        include_trace_handler=False,
    )
    for step_type in (StepType.ANALYZE_ADDRESS, StepType.ANALYZE_TRANSACTION):
        registry.register(
            ProviderAnalysisStepHandler(
                repository, step_type, configured, provider_runner
            )
        )
    registry.register(ProviderTraceStepHandler(repository, configured))
    return registry
