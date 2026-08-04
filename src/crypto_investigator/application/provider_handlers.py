from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

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
from crypto_investigator.planner.models import PlanStep, StepType
from crypto_investigator.providers.service import analyze_provider_identifier


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


def create_desktop_execution_registry(
    repository: CaseRepository,
    *,
    settings: Settings | None = None,
    provider_runner: ProviderRunner = analyze_provider_identifier,
):
    configured = settings or load_config()
    registry = create_offline_execution_registry(
        repository, include_analysis_handlers=False
    )
    for step_type in (StepType.ANALYZE_ADDRESS, StepType.ANALYZE_TRANSACTION):
        registry.register(
            ProviderAnalysisStepHandler(
                repository, step_type, configured, provider_runner
            )
        )
    return registry
