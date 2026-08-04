from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_errors import (
    ArtifactValidationError,
    ExecutionCancelledError,
    ExecutionGateError,
    ResumeNotAllowedError,
    RetryNotAllowedError,
    UnknownStepHandlerError,
)
from crypto_investigator.application.execution_events import EventType, ExecutionEvent
from crypto_investigator.application.execution_models import (
    CancellationToken,
    CaseExecution,
    CaseExecutionResult,
    ExecutionFailure,
    ExecutionStatus,
    ExecutionStepStatus,
    FailureKind,
    StepExecution,
    utc_now,
)
from crypto_investigator.application.execution_policy import failure_kind_for
from crypto_investigator.application.execution_registry import ExecutionRegistry
from crypto_investigator.cases import AuditLog, CaseRepository, CaseStatus
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.planner import (
    InvestigationPlan,
    StepStatus,
    StepType,
    executable_steps,
    validate_plan,
)
from crypto_investigator.services.artifact_service import ArtifactService
from crypto_investigator.services.execution_state_service import ExecutionStateService
from crypto_investigator.services.step_dispatcher import StepDispatcher

EventCallback = Callable[[ExecutionEvent], None]


class CaseExecutionService:
    MAX_RETRIES = 3

    def __init__(
        self,
        repository: CaseRepository,
        registry: ExecutionRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or ExecutionRegistry()
        self.dispatcher = StepDispatcher(self.registry)
        self.state = ExecutionStateService(repository)
        self._tokens: dict[str, CancellationToken] = {}

    def create_execution(self, case_id: str, plan_id: str) -> CaseExecution:
        case, plan = self._load_and_gate_plan(case_id, plan_id)
        for step in executable_steps(plan):
            try:
                self.registry.get(step.step_type)
            except UnknownStepHandlerError as exc:
                raise ExecutionGateError(str(exc)) from exc
        execution = CaseExecution(
            execution_id=f"execution_{uuid4().hex}",
            case_id=case_id,
            plan_id=plan.plan_id,
            plan_version=plan.plan_version,
            steps=[
                StepExecution(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    order=step.order,
                    status=(
                        ExecutionStepStatus.PENDING
                        if step.enabled
                        else ExecutionStepStatus.SKIPPED
                    ),
                    skipped_reason=None if step.enabled else "Disabled in confirmed plan",
                    provider=step.provider,
                )
                for step in plan.steps
            ],
            settings_snapshot=dict(plan.settings_snapshot),
        )
        self.state.create_layout(execution)
        for step in execution.steps:
            self.state.save_step(execution, step)
        self._update_case_summary(execution)
        self._audit(
            execution,
            "execution_created",
            "Execution created",
            {"plan_id": plan.plan_id, "plan_version": plan.plan_version},
        )
        return execution

    def run_execution(
        self,
        execution_id: str,
        event_callback: EventCallback | None = None,
    ) -> CaseExecutionResult:
        execution = self.state.load(execution_id)
        case, plan = self._load_and_gate_plan(
            execution.case_id, execution.plan_id, execution.plan_version
        )
        if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING}:
            raise ExecutionGateError(
                f"Execution cannot run from status: {execution.status.value}"
            )
        token = self._tokens.setdefault(execution_id, CancellationToken())
        if token.is_cancelled or execution.status is ExecutionStatus.CANCELLED:
            return CaseExecutionResult(
                execution=execution,
                artifacts=execution.artifacts,
                success=False,
            )
        execution = execution.model_copy(
            update={
                "status": ExecutionStatus.RUNNING,
                "started_at": execution.started_at or utc_now(),
                "completed_at": None,
            }
        )
        self.state.save(execution)
        self._update_case_summary(execution)
        self._audit(execution, "execution_started", "Execution started")
        self._emit(
            execution,
            EventType.EXECUTION_STARTED,
            "execution",
            execution.status.value,
            "Execution started",
            callback=event_callback,
        )

        plan_by_id = {step.step_id: step for step in plan.steps}
        for index, step_state in enumerate(execution.steps):
            if step_state.status in {
                ExecutionStepStatus.COMPLETED,
                ExecutionStepStatus.SKIPPED,
            }:
                continue
            plan_step = plan_by_id.get(step_state.step_id)
            if plan_step is None or not plan_step.enabled:
                continue
            execution, stop = self._execute_step(
                execution, case, plan_step, index, token, event_callback
            )
            if stop:
                break

        if execution.status is ExecutionStatus.RUNNING:
            has_partial = any(
                step.status
                in {
                    ExecutionStepStatus.PARTIAL,
                    ExecutionStepStatus.WARNING,
                    ExecutionStepStatus.FAILED,
                }
                for step in execution.steps
            )
            final_status = (
                ExecutionStatus.PARTIAL if has_partial else ExecutionStatus.COMPLETED
            )
            execution = execution.model_copy(
                update={
                    "status": final_status,
                    "current_step_id": None,
                    "completed_at": utc_now(),
                }
            )
            event_type = (
                EventType.EXECUTION_PARTIAL
                if final_status is ExecutionStatus.PARTIAL
                else EventType.EXECUTION_COMPLETED
            )
            self._emit(
                execution,
                event_type,
                "execution",
                final_status.value,
                f"Execution {final_status.value}",
                callback=event_callback,
            )
            self._audit(
                execution,
                "execution_completed",
                f"Execution {final_status.value}",
                {"status": final_status.value},
            )
        self.state.save(execution)
        ArtifactService(self.repository.workspace(execution.case_id)).save_manifest(
            execution.execution_id, execution.artifacts
        )
        self._update_case_summary(execution)
        return CaseExecutionResult(
            execution=execution,
            artifacts=execution.artifacts,
            success=execution.status is ExecutionStatus.COMPLETED,
        )

    def cancel_execution(self, execution_id: str, reason: str) -> CaseExecution:
        execution = self.state.load(execution_id)
        if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED}:
            raise ExecutionGateError("Terminal execution cannot be cancelled")
        token = self._tokens.setdefault(execution_id, CancellationToken())
        token.request_cancel(str(redact_sensitive(reason)))
        if execution.status is ExecutionStatus.RUNNING and execution.current_step_id:
            try:
                case, plan = self._load_and_gate_plan(
                    execution.case_id, execution.plan_id, execution.plan_version
                )
                plan_step = next(
                    item
                    for item in plan.steps
                    if item.step_id == execution.current_step_id
                )
                step_state = next(
                    item
                    for item in execution.steps
                    if item.step_id == execution.current_step_id
                )
                execution_dir = self.state.execution_dir(
                    execution.case_id, execution.execution_id
                )
                context = ExecutionContext(
                    case=case,
                    execution=execution,
                    execution_dir=execution_dir,
                    step_dir=self.state.step_dir(
                        execution, step_state.order, step_state.step_id
                    ),
                    artifacts_dir=execution_dir / "artifacts",
                    checkpoints_dir=execution_dir / "checkpoints",
                    cancellation_token=token,
                )
                self.dispatcher.cancel(plan_step, context)
            except Exception:
                self.state.append_log(
                    execution,
                    step_id=execution.current_step_id,
                    level="WARNING",
                    message="Step cancellation notification failed",
                )
        if execution.status is not ExecutionStatus.RUNNING:
            execution = execution.model_copy(
                update={
                    "status": ExecutionStatus.CANCELLED,
                    "cancelled_at": token.cancelled_at,
                    "cancellation_reason": token.reason,
                    "completed_at": token.cancelled_at,
                }
            )
            self.state.save(execution)
            self._update_case_summary(execution)
            self._emit(
                execution,
                EventType.EXECUTION_CANCELLED,
                "execution",
                "cancelled",
                "Execution cancelled",
            )
            self._audit(execution, "execution_cancelled", "Execution cancelled")
        return execution

    def resume_execution(
        self,
        execution_id: str,
        event_callback: EventCallback | None = None,
    ) -> CaseExecutionResult:
        execution = self.state.load(execution_id)
        if execution.status not in {
            ExecutionStatus.CANCELLED,
            ExecutionStatus.SUSPENDED,
            ExecutionStatus.PARTIAL,
            ExecutionStatus.FAILED,
        }:
            raise ResumeNotAllowedError(
                f"Cannot resume execution from {execution.status.value}"
            )
        _, plan = self._load_and_gate_plan(
            execution.case_id, execution.plan_id, execution.plan_version
        )
        artifacts = ArtifactService(self.repository.workspace(execution.case_id))
        if any(not artifacts.verify(item) for item in execution.artifacts):
            raise ResumeNotAllowedError("Artifact integrity verification failed")
        plan_by_id = {step.step_id: step for step in plan.steps}
        steps = []
        for step in execution.steps:
            if step.status is ExecutionStepStatus.COMPLETED:
                steps.append(step)
                continue
            plan_step = plan_by_id.get(step.step_id)
            if plan_step is None or not plan_step.enabled:
                steps.append(step)
                continue
            handler = self.registry.get(plan_step.step_type)
            if step.status in {
                ExecutionStepStatus.FAILED,
                ExecutionStepStatus.PARTIAL,
                ExecutionStepStatus.CANCELLED,
                ExecutionStepStatus.RUNNING,
            } and (handler.resume_supported or handler.retry_supported):
                steps.append(
                    step.model_copy(
                        update={
                            "status": ExecutionStepStatus.PENDING,
                            "failure": None,
                        }
                    )
                )
            else:
                steps.append(step)
        execution = execution.model_copy(
            update={
                "steps": steps,
                "status": ExecutionStatus.PARTIAL,
                "cancelled_at": None,
                "cancellation_reason": None,
                "resume_count": execution.resume_count + 1,
                "completed_at": None,
            }
        )
        self._tokens[execution_id] = CancellationToken()
        self.state.save(execution)
        self._emit(
            execution,
            EventType.EXECUTION_RESUMED,
            "execution",
            "partial",
            "Execution resumed",
            callback=event_callback,
        )
        self._audit(execution, "execution_resumed", "Execution resumed")
        return self.run_execution(execution_id, event_callback)

    def retry_step(
        self,
        execution_id: str,
        step_id: str,
        event_callback: EventCallback | None = None,
    ) -> StepExecution:
        execution = self.state.load(execution_id)
        case, plan = self._load_and_gate_plan(
            execution.case_id, execution.plan_id, execution.plan_version
        )
        index = next(
            (i for i, item in enumerate(execution.steps) if item.step_id == step_id),
            None,
        )
        if index is None:
            raise RetryNotAllowedError(f"Unknown step: {step_id}")
        state = execution.steps[index]
        if state.status not in {
            ExecutionStepStatus.FAILED,
            ExecutionStepStatus.PARTIAL,
            ExecutionStepStatus.CANCELLED,
        }:
            raise RetryNotAllowedError("Only failed, partial, or cancelled steps can retry")
        if state.retry_count >= self.MAX_RETRIES:
            raise RetryNotAllowedError("Retry limit reached")
        plan_step = next(item for item in plan.steps if item.step_id == step_id)
        handler = self.registry.get(plan_step.step_type)
        if not handler.retry_supported or (
            state.failure is not None and not state.failure.retryable
        ):
            raise RetryNotAllowedError("Step failure is not retryable")
        steps = list(execution.steps)
        steps[index] = state.model_copy(
            update={
                "status": ExecutionStepStatus.PENDING,
                "retry_count": state.retry_count + 1,
                "failure": None,
            }
        )
        execution = execution.model_copy(
            update={"steps": steps, "status": ExecutionStatus.RUNNING}
        )
        self.state.save(execution)
        self._audit(
            execution,
            "step_retried",
            "Step retry started",
            {"step_id": step_id, "retry_count": steps[index].retry_count},
        )
        token = CancellationToken()
        execution, _ = self._execute_step(
            execution, case, plan_step, index, token, event_callback
        )
        has_failure = any(
            item.status
            in {
                ExecutionStepStatus.FAILED,
                ExecutionStepStatus.PARTIAL,
                ExecutionStepStatus.CANCELLED,
            }
            for item in execution.steps
        )
        execution = execution.model_copy(
            update={
                "status": (
                    ExecutionStatus.PARTIAL
                    if has_failure
                    else ExecutionStatus.COMPLETED
                ),
                "current_step_id": None,
                "completed_at": utc_now(),
            }
        )
        self.state.save(execution)
        self._update_case_summary(execution)
        return execution.steps[index]

    def get_execution(self, execution_id: str) -> CaseExecution:
        return self.state.load(execution_id)

    def list_executions(self, case_id: str) -> tuple[CaseExecution, ...]:
        case = self.repository.load(case_id)
        executions = []
        for summary in case.executions:
            try:
                executions.append(self.state.load(summary["execution_id"], case_id))
            except Exception:
                continue
        return tuple(sorted(executions, key=lambda item: item.created_at))

    def get_execution_events(self, execution_id: str) -> tuple[ExecutionEvent, ...]:
        execution = self.state.load(execution_id)
        return self.state.events(execution)

    def get_execution_artifacts(self, execution_id: str):
        return tuple(self.state.load(execution_id).artifacts)

    def _execute_step(
        self,
        execution: CaseExecution,
        case,
        plan_step,
        index: int,
        token: CancellationToken,
        callback: EventCallback | None,
    ) -> tuple[CaseExecution, bool]:
        started = utc_now()
        clock = monotonic()
        states = list(execution.steps)
        state = states[index].model_copy(
            update={
                "status": ExecutionStepStatus.RUNNING,
                "started_at": started,
                "completed_at": None,
            }
        )
        states[index] = state
        execution = execution.model_copy(
            update={"steps": states, "current_step_id": plan_step.step_id}
        )
        self.state.save(execution)
        self.state.save_step(execution, state)
        self._emit(
            execution,
            EventType.STEP_STARTED,
            plan_step.step_type.value,
            "running",
            "Step started",
            step_id=plan_step.step_id,
            provider=plan_step.provider,
            callback=callback,
        )
        self._audit(
            execution,
            "step_started",
            "Step started",
            {"step_id": plan_step.step_id, "step_type": plan_step.step_type.value},
        )
        execution_dir = self.state.execution_dir(
            execution.case_id, execution.execution_id
        )
        context = ExecutionContext(
            case=case,
            execution=execution,
            execution_dir=execution_dir,
            step_dir=self.state.step_dir(execution, state.order, state.step_id),
            artifacts_dir=execution_dir / "artifacts",
            checkpoints_dir=execution_dir / "checkpoints",
            cancellation_token=token,
        )
        try:
            result = self.dispatcher.dispatch(case, plan_step, context)
            handler = self.registry.get(plan_step.step_type)
            produced_types = {item.artifact_type.value for item in result.artifacts}
            missing = set(handler.expected_artifacts) - produced_types
            if missing:
                raise ArtifactValidationError(
                    f"Expected artifacts missing: {', '.join(sorted(missing))}"
                )
            registered = []
            artifact_service = ArtifactService(
                self.repository.workspace(execution.case_id)
            )
            for candidate in result.artifacts:
                artifact = artifact_service.register(
                    execution_id=execution.execution_id,
                    step_id=state.step_id,
                    candidate=candidate,
                )
                registered.append(artifact)
                self._emit(
                    execution,
                    EventType.ARTIFACT_CREATED,
                    plan_step.step_type.value,
                    "completed",
                    "Artifact registered",
                    step_id=state.step_id,
                    artifacts=[artifact.artifact_id],
                    callback=callback,
                )
                self._audit(
                    execution,
                    "artifact_registered",
                    "Artifact registered",
                    {
                        "step_id": state.step_id,
                        "artifact_id": artifact.artifact_id,
                        "relative_path": artifact.relative_path,
                    },
                )
            checkpoint = result.checkpoint
            if checkpoint is not None:
                checkpoint = self.state.save_checkpoint(execution, checkpoint)
                self._emit(
                    execution,
                    EventType.CHECKPOINT_SAVED,
                    plan_step.step_type.value,
                    "completed",
                    "Checkpoint saved",
                    step_id=state.step_id,
                    callback=callback,
                )
            if result.records_processed:
                self._emit(
                    execution,
                    EventType.RECORDS_UPDATED,
                    plan_step.step_type.value,
                    "running",
                    "Records processed",
                    step_id=state.step_id,
                    current_records=result.records_processed,
                    safe_details=result.safe_details,
                    callback=callback,
                )
            is_partial = result.partial or result.status in {
                ExecutionStepStatus.PARTIAL,
                ExecutionStepStatus.WARNING,
            }
            status = (
                ExecutionStepStatus.PARTIAL
                if is_partial
                else ExecutionStepStatus.COMPLETED
            )
            state = state.model_copy(
                update={
                    "status": status,
                    "completed_at": utc_now(),
                    "elapsed_seconds": monotonic() - clock,
                    "output_refs": [item.artifact_id for item in registered],
                    "artifacts": [item.artifact_id for item in registered],
                    "warnings": result.warnings,
                    "records_processed": result.records_processed,
                    "partial": is_partial,
                    "checkpoint": checkpoint,
                    "failure": None,
                }
            )
            states = list(execution.steps)
            states[index] = state
            execution = execution.model_copy(
                update={
                    "steps": states,
                    "artifacts": [*execution.artifacts, *registered],
                    "warnings": [*execution.warnings, *result.warnings],
                }
            )
            event_type = (
                EventType.STEP_PARTIAL if is_partial else EventType.STEP_COMPLETED
            )
            audit_action = "step_partial" if is_partial else "step_completed"
            self._emit(
                execution,
                event_type,
                plan_step.step_type.value,
                status.value,
                f"Step {status.value}",
                step_id=state.step_id,
                current_records=result.records_processed,
                warnings_count=len(result.warnings),
                artifacts=state.artifacts,
                safe_details=result.safe_details,
                callback=callback,
            )
            self._audit(
                execution,
                audit_action,
                f"Step {status.value}",
                {"step_id": state.step_id, "records_processed": result.records_processed},
            )
            if plan_step.step_type is StepType.REQUEST_MANUAL_REVIEW:
                execution = execution.model_copy(
                    update={
                        "status": ExecutionStatus.SUSPENDED,
                        "current_step_id": None,
                    }
                )
                self._emit(
                    execution,
                    EventType.EXECUTION_SUSPENDED,
                    "execution",
                    "suspended",
                    "Execution suspended for manual review",
                    callback=callback,
                )
                self._audit(
                    execution,
                    "execution_suspended",
                    "Execution suspended for manual review",
                )
                stop = True
            else:
                stop = False
        except ExecutionCancelledError as exc:
            failure = ExecutionFailure(
                kind=FailureKind.CANCELLED,
                safe_message=str(redact_sensitive(str(exc))),
                step_id=state.step_id,
                retryable=True,
            )
            state = state.model_copy(
                update={
                    "status": ExecutionStepStatus.CANCELLED,
                    "completed_at": utc_now(),
                    "elapsed_seconds": monotonic() - clock,
                    "failure": failure,
                }
            )
            states = list(execution.steps)
            states[index] = state
            execution = execution.model_copy(
                update={
                    "steps": states,
                    "status": ExecutionStatus.CANCELLED,
                    "failures": [*execution.failures, failure],
                    "cancelled_at": token.cancelled_at or utc_now(),
                    "cancellation_reason": token.reason or "Execution cancelled",
                    "completed_at": token.cancelled_at or utc_now(),
                    "current_step_id": None,
                }
            )
            self._emit(
                execution,
                EventType.STEP_CANCELLED,
                plan_step.step_type.value,
                "cancelled",
                "Step cancelled",
                step_id=state.step_id,
                callback=callback,
            )
            self._emit(
                execution,
                EventType.EXECUTION_CANCELLED,
                "execution",
                "cancelled",
                "Execution cancelled",
                callback=callback,
            )
            self._audit(execution, "execution_cancelled", "Execution cancelled")
            stop = True
        except Exception as exc:
            kind = failure_kind_for(plan_step.step_type)
            handler = self.registry.get(plan_step.step_type)
            failure = ExecutionFailure(
                kind=kind,
                safe_message=str(redact_sensitive(str(exc))) or type(exc).__name__,
                step_id=state.step_id,
                retryable=bool(handler.retry_supported and kind is not FailureKind.FATAL),
                code=type(exc).__name__,
            )
            state = state.model_copy(
                update={
                    "status": ExecutionStepStatus.FAILED,
                    "completed_at": utc_now(),
                    "elapsed_seconds": monotonic() - clock,
                    "failure": failure,
                }
            )
            states = list(execution.steps)
            states[index] = state
            updates = {
                "steps": states,
                "failures": [*execution.failures, failure],
            }
            stop = kind is FailureKind.FATAL
            if stop:
                updates.update(
                    {
                        "status": ExecutionStatus.FAILED,
                        "completed_at": utc_now(),
                        "current_step_id": None,
                    }
                )
            execution = execution.model_copy(update=updates)
            self._emit(
                execution,
                EventType.STEP_FAILED,
                plan_step.step_type.value,
                "failed",
                failure.safe_message,
                step_id=state.step_id,
                safe_details={"error_type": failure.code, "kind": kind.value},
                callback=callback,
            )
            self._audit(
                execution,
                "step_failed",
                "Step failed",
                {"step_id": state.step_id, "kind": kind.value, "code": failure.code},
            )
            if stop:
                self._emit(
                    execution,
                    EventType.EXECUTION_FAILED,
                    "execution",
                    "failed",
                    "Execution failed",
                    callback=callback,
                )
                self._audit(execution, "execution_failed", "Execution failed")
        self.state.save_step(execution, state)
        self.state.save(execution)
        return execution, stop

    def _load_and_gate_plan(
        self,
        case_id: str,
        plan_id: str,
        expected_version: int | None = None,
    ):
        case = self.repository.load(case_id)
        if case.status is CaseStatus.ARCHIVED:
            raise ExecutionGateError("Archived case cannot execute")
        matching = [item for item in case.plans if item.get("plan_id") == plan_id]
        if len(matching) != 1:
            raise ExecutionGateError(f"Plan not found: {plan_id}")
        plan = InvestigationPlan.model_validate(matching[0])
        try:
            validate_plan(plan)
            allowed = executable_steps(plan)
        except Exception as exc:
            raise ExecutionGateError(str(exc)) from exc
        if expected_version is not None and plan.plan_version != expected_version:
            raise ExecutionGateError("Plan version mismatch")
        if any(
            step.enabled
            and step.step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP
            for step in plan.steps
        ):
            raise ExecutionGateError("Unsupported step cannot execute")
        enabled_supported = [
            step
            for step in plan.steps
            if step.enabled
            and step.step_type is not StepType.UNSUPPORTED_RECOMMENDED_STEP
        ]
        if len(allowed) != len(enabled_supported):
            raise ExecutionGateError(
                "Every enabled step must be approved before execution"
            )
        return case, plan

    def _update_case_summary(self, execution: CaseExecution) -> None:
        case = self.repository.load(execution.case_id)
        summary = {
            "execution_id": execution.execution_id,
            "plan_id": execution.plan_id,
            "plan_version": execution.plan_version,
            "status": execution.status.value,
            "created_at": execution.created_at.isoformat(),
            "completed_at": (
                execution.completed_at.isoformat() if execution.completed_at else None
            ),
            "artifact_count": len(execution.artifacts),
            "failure_count": len(execution.failures),
        }
        executions = [
            item
            for item in case.executions
            if item.get("execution_id") != execution.execution_id
        ]
        executions.append(summary)
        active = (
            execution.execution_id
            if execution.status in {ExecutionStatus.PENDING, ExecutionStatus.RUNNING}
            else None
        )
        self.repository.save(
            case.model_copy(
                update={
                    "executions": executions,
                    "latest_execution_id": execution.execution_id,
                    "active_execution_id": active,
                    "last_execution_status": execution.status.value,
                    "execution_summary": summary,
                }
            )
        )

    def _audit(
        self,
        execution: CaseExecution,
        action: str,
        description: str,
        metadata: dict | None = None,
    ) -> None:
        AuditLog(self.repository.workspace(execution.case_id)).append(
            action=action,
            object_type="execution",
            object_id=execution.execution_id,
            description=description,
            metadata=metadata,
        )

    def _emit(
        self,
        execution: CaseExecution,
        event_type: EventType,
        stage: str,
        status: str,
        message: str,
        *,
        step_id: str | None = None,
        callback: EventCallback | None = None,
        **kwargs,
    ) -> ExecutionEvent:
        sequence = len(self.state.events(execution)) + 1
        event = ExecutionEvent(
            event_id=f"event_{sequence:08d}",
            execution_id=execution.execution_id,
            case_id=execution.case_id,
            step_id=step_id,
            event_type=event_type,
            stage=stage,
            status=status,
            message=message,
            **kwargs,
        )
        self.state.append_event(event)
        if callback is not None:
            try:
                callback(event)
            except Exception:
                self.state.append_log(
                    execution,
                    step_id=step_id,
                    level="WARNING",
                    message="Execution event observer failed",
                )
        return event
