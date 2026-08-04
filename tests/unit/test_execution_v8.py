from __future__ import annotations

import json
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from crypto_investigator.application import (
    ArtifactCandidate,
    ArtifactType,
    CancellationToken,
    CaseExecution,
    CaseExecutionService,
    Completeness,
    EventType,
    ExecutionArtifact,
    ExecutionCheckpoint,
    ExecutionEvent,
    ExecutionRegistry,
    ExecutionStatus,
    ExecutionStepStatus,
    StepExecution,
    StepExecutionResult,
)
from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_errors import (
    ArtifactValidationError,
    ExecutionCancelledError,
    ExecutionGateError,
    ResumeNotAllowedError,
    RetryNotAllowedError,
    UnknownStepHandlerError,
)
from crypto_investigator.cases import AuditLog, CaseRepository, new_case_id
from crypto_investigator.domain import Chain
from crypto_investigator.planner import (
    GoalType,
    InvestigationGoal,
    InvestigationPlan,
    PlanStep,
    PlannerType,
    StepStatus,
    StepType,
)
from crypto_investigator.services import (
    ArtifactService,
    ExecutionStateService,
    StepDispatcher,
)


class MockHandler:
    resume_supported = True
    retry_supported = True
    expected_artifacts = ("other",)

    def __init__(
        self,
        step_type: StepType,
        *,
        behavior: str = "success",
        retry_supported: bool = True,
    ) -> None:
        self.supported_step_type = step_type
        self.behavior = behavior
        self.retry_supported = retry_supported
        self.calls = 0
        self.cancel_calls = 0
        self.validation_calls = 0

    def validate_input(self, case, step, context) -> None:
        self.validation_calls += 1
        if self.behavior == "validation_failure":
            raise ValueError("invalid handler input")

    def execute(self, case, step, context, cancellation_token) -> StepExecutionResult:
        self.calls += 1
        if self.behavior == "cancel":
            cancellation_token.request_cancel("mock cancellation")
            cancellation_token.raise_if_cancelled()
        if self.behavior == "failure":
            raise RuntimeError("safe mock failure")
        if self.behavior == "secret_failure":
            raise RuntimeError(
                r"Bearer super-secret-token failed at C:\Users\private\input.csv"
            )
        path = context.artifacts_dir / f"{step.step_id}_{self.calls}.json"
        path.write_text('{"ok":true}', encoding="utf-8")
        candidate = ArtifactCandidate(
            artifact_type=ArtifactType.OTHER,
            relative_path=f"artifacts/{path.name}",
            source="mock",
        )
        partial = self.behavior == "partial"
        return StepExecutionResult(
            status=(
                ExecutionStepStatus.PARTIAL
                if partial
                else ExecutionStepStatus.COMPLETED
            ),
            artifacts=[candidate],
            records_processed=5,
            partial=partial,
        )

    def cancel(self, context) -> None:
        self.cancel_calls += 1


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    return CaseRepository(tmp_path / "cases")


def make_plan(
    case_id: str,
    step_types: tuple[StepType, ...] = (StepType.DETECT_CHAIN,),
    *,
    confirmed: bool = True,
    plan_version: int = 1,
    statuses: dict[StepType, StepStatus] | None = None,
    enabled: dict[StepType, bool] | None = None,
) -> InvestigationPlan:
    statuses = statuses or {}
    enabled = enabled or {}
    steps = []
    for index, step_type in enumerate(step_types, 1):
        prerequisites = []
        if step_type is StepType.GENERATE_NARRATIVE:
            investigation = next(
                (
                    item
                    for item in steps
                    if item.step_type is StepType.RUN_INVESTIGATION_FEATURES
                ),
                None,
            )
            if investigation is not None:
                prerequisites = [investigation.step_id]
        steps.append(PlanStep(
            step_id=f"step_{index}_{step_type.value}",
            order=index,
            title=step_type.value,
            step_type=step_type,
            status=statuses.get(
                step_type, StepStatus.APPROVED if confirmed else StepStatus.PROPOSED
            ),
            target_type="case",
            target_ids=[case_id],
            chain=(
                Chain.TRON
                if step_type
                in {StepType.ANALYZE_ADDRESS, StepType.ANALYZE_TRANSACTION}
                else None
            ),
            reason="mock execution plan",
            enabled=enabled.get(step_type, True),
            requires_confirmation=step_type is StepType.GENERATE_NARRATIVE,
            prerequisites=prerequisites,
        ))
    return InvestigationPlan(
        plan_id="plan_execution_fixture",
        case_id=case_id,
        generated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        planner_type=PlannerType.DETERMINISTIC,
        goals=[
            InvestigationGoal(
                goal_id="goal_execution",
                goal_type=GoalType.CUSTOM,
                title="Execution fixture",
                confirmed_by_user=True,
            )
        ],
        steps=steps,
        confirmed_at=(
            datetime(2026, 8, 4, tzinfo=timezone.utc) if confirmed else None
        ),
        confirmed_by="analyst" if confirmed else None,
        plan_version=plan_version,
        settings_snapshot={
            "max_pages": 10,
            "max_records": 100,
            "cache": True,
            "ai_enabled": False,
        },
    )


def save_plan(repository: CaseRepository, plan: InvestigationPlan):
    case = repository.load(plan.case_id)
    return repository.save(
        case.model_copy(update={"plans": [plan.model_dump(mode="json")]})
    )


def build_service(
    repository: CaseRepository,
    step_types: tuple[StepType, ...] = (StepType.DETECT_CHAIN,),
    *,
    behavior: dict[StepType, str] | None = None,
):
    case = repository.create("Execution case")
    plan = make_plan(case.case_id, step_types)
    save_plan(repository, plan)
    registry = ExecutionRegistry()
    handlers = {}
    for step_type in step_types:
        handler = MockHandler(
            step_type, behavior=(behavior or {}).get(step_type, "success")
        )
        registry.register(handler)
        handlers[step_type] = handler
    return case, plan, CaseExecutionService(repository, registry), handlers


@pytest.mark.parametrize("status", list(ExecutionStatus))
def test_execution_model_status_round_trip(status: ExecutionStatus) -> None:
    model = CaseExecution(
        execution_id="execution_" + "a" * 32,
        case_id=new_case_id(),
        plan_id="plan_x",
        plan_version=1,
        status=status,
    )
    assert CaseExecution.model_validate_json(model.model_dump_json()).status is status


@pytest.mark.parametrize("status", list(ExecutionStepStatus))
def test_step_execution_status_round_trip(status: ExecutionStepStatus) -> None:
    step = StepExecution(
        step_id="step_x",
        step_type=StepType.DETECT_CHAIN,
        order=1,
        status=status,
    )
    assert StepExecution.model_validate_json(step.model_dump_json()).status is status


@pytest.mark.parametrize("artifact_type", list(ArtifactType))
def test_artifact_model_types(artifact_type: ArtifactType) -> None:
    artifact = ExecutionArtifact(
        case_id=new_case_id(),
        execution_id="execution_" + "b" * 32,
        step_id="step_x",
        artifact_type=artifact_type,
        relative_path="executions/execution_" + "b" * 32 + "/artifacts/a",
        sha256="a" * 64,
        size=1,
        source="test",
    )
    assert artifact.artifact_type is artifact_type


@pytest.mark.parametrize("event_type", list(EventType))
def test_execution_event_types(event_type: EventType) -> None:
    event = ExecutionEvent(
        event_id="event_00000001",
        execution_id="execution_" + "c" * 32,
        case_id=new_case_id(),
        event_type=event_type,
        stage="test",
        status="pending",
        message="safe",
    )
    assert ExecutionEvent.model_validate_json(event.model_dump_json()).event_type is event_type


def test_checkpoint_model_round_trip() -> None:
    item = ExecutionCheckpoint(
        execution_id="execution_" + "a" * 32,
        step_id="step_x",
        checkpoint_type="cursor",
        completed_units=10,
        next_cursor="next",
    )
    assert ExecutionCheckpoint.model_validate_json(item.model_dump_json()) == item


def test_cancellation_token() -> None:
    token = CancellationToken()
    assert token.is_cancelled is False
    token.request_cancel("stop")
    assert token.is_cancelled is True
    assert token.cancelled_at is not None
    with pytest.raises(ExecutionCancelledError):
        token.raise_if_cancelled()


def test_registry_registration_and_duplicate() -> None:
    registry = ExecutionRegistry()
    registry.register(MockHandler(StepType.DETECT_CHAIN))
    assert registry.step_types() == (StepType.DETECT_CHAIN,)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(MockHandler(StepType.DETECT_CHAIN))


def test_dispatcher_unknown_handler(repository: CaseRepository) -> None:
    case = repository.create("Case")
    execution = CaseExecution(
        execution_id="execution_" + "d" * 32,
        case_id=case.case_id,
        plan_id="plan",
        plan_version=1,
    )
    path = repository.workspace(case.case_id).path
    context = ExecutionContext(
        case, execution, path, path, path, path, CancellationToken()
    )
    with pytest.raises(UnknownStepHandlerError):
        StepDispatcher(ExecutionRegistry()).dispatch(
            case, make_plan(case.case_id).steps[0], context
        )


def test_handler_validation_and_execution(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(repository)
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    handler = handlers[StepType.DETECT_CHAIN]
    assert handler.validation_calls == 1
    assert handler.calls == 1
    assert result.execution.status is ExecutionStatus.COMPLETED


def test_unconfirmed_plan_rejected(repository: CaseRepository) -> None:
    case = repository.create("Case")
    plan = make_plan(case.case_id, confirmed=False)
    save_plan(repository, plan)
    with pytest.raises(ExecutionGateError):
        CaseExecutionService(repository).create_execution(case.case_id, plan.plan_id)


def test_archived_case_rejected(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    repository.archive(case.case_id)
    with pytest.raises(ExecutionGateError, match="Archived"):
        service.create_execution(case.case_id, plan.plan_id)


def test_unknown_handler_rejected_at_gate(repository: CaseRepository) -> None:
    case = repository.create("Case")
    plan = make_plan(case.case_id)
    save_plan(repository, plan)
    with pytest.raises(ExecutionGateError, match="No handler"):
        CaseExecutionService(repository).create_execution(case.case_id, plan.plan_id)


def test_unapproved_ai_step_rejected(repository: CaseRepository) -> None:
    case = repository.create("Case")
    plan = make_plan(
        case.case_id,
        (StepType.RUN_INVESTIGATION_FEATURES, StepType.GENERATE_NARRATIVE),
        statuses={StepType.GENERATE_NARRATIVE: StepStatus.PROPOSED},
    )
    save_plan(repository, plan)
    registry = ExecutionRegistry()
    registry.register(MockHandler(StepType.RUN_INVESTIGATION_FEATURES))
    registry.register(MockHandler(StepType.GENERATE_NARRATIVE))
    with pytest.raises(ExecutionGateError, match="approved"):
        CaseExecutionService(repository, registry).create_execution(
            case.case_id, plan.plan_id
        )


def test_execution_create_layout_and_case_update(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    directory = service.state.execution_dir(case.case_id, execution.execution_id)
    assert (directory / "execution.json").is_file()
    assert all((directory / name).is_dir() for name in ("steps", "artifacts", "logs", "checkpoints"))
    updated = repository.load(case.case_id)
    assert updated.active_execution_id == execution.execution_id


def test_execution_success_events_artifact_and_audit(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(
        repository,
        (
            StepType.DETECT_CHAIN,
            StepType.COMPARE_KNOWN_ADDRESSES,
            StepType.BUILD_GRAPH,
            StepType.RUN_INVESTIGATION_FEATURES,
            StepType.EXPORT_EVIDENCE_MANIFEST,
        ),
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    observed = []
    result = service.run_execution(execution.execution_id, observed.append)
    assert result.execution.status is ExecutionStatus.COMPLETED
    assert len(result.artifacts) == 5
    assert observed[0].event_type is EventType.EXECUTION_STARTED
    assert observed[-1].event_type is EventType.EXECUTION_COMPLETED
    assert AuditLog(repository.workspace(case.case_id)).verify()
    assert repository.load(case.case_id).last_execution_status == "completed"


def test_event_ordering_is_monotonic(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    events = service.get_execution_events(execution.execution_id)
    assert [item.event_id for item in events] == [
        f"event_{index:08d}" for index in range(1, len(events) + 1)
    ]


def test_event_safe_details_redaction(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(
        repository,
        (StepType.BUILD_GRAPH,),
        behavior={StepType.BUILD_GRAPH: "secret_failure"},
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    content = (
        service.state.execution_dir(case.case_id, execution.execution_id)
        / "events.jsonl"
    ).read_text(encoding="utf-8")
    assert "super-secret-token" not in content
    assert r"C:\Users" not in content
    assert "Traceback" not in content


def test_partial_step_and_execution(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(
        repository,
        (StepType.ANALYZE_ADDRESS, StepType.RUN_INVESTIGATION_FEATURES),
        behavior={StepType.ANALYZE_ADDRESS: "partial"},
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.PARTIAL
    assert result.execution.steps[0].status is ExecutionStepStatus.PARTIAL
    assert result.execution.steps[1].status is ExecutionStepStatus.COMPLETED


def test_fatal_failure_stops_later_steps(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (StepType.VALIDATE_CASE_INPUTS, StepType.DETECT_CHAIN),
        behavior={StepType.VALIDATE_CASE_INPUTS: "failure"},
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.FAILED
    assert handlers[StepType.DETECT_CHAIN].calls == 0
    assert result.execution.failures[0].kind.value == "fatal"


@pytest.mark.parametrize(
    "step_type",
    [StepType.BUILD_GRAPH, StepType.EXPORT_EVIDENCE_MANIFEST],
)
def test_recoverable_failure_continues(
    repository: CaseRepository, step_type: StepType
) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (step_type, StepType.DETECT_CHAIN),
        behavior={step_type: "failure"},
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.PARTIAL
    assert handlers[StepType.DETECT_CHAIN].calls == 1


def test_narrative_failure_is_recoverable(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (
            StepType.RUN_INVESTIGATION_FEATURES,
            StepType.GENERATE_NARRATIVE,
            StepType.DETECT_CHAIN,
        ),
        behavior={StepType.GENERATE_NARRATIVE: "failure"},
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.PARTIAL
    assert handlers[StepType.DETECT_CHAIN].calls == 1


def test_manual_review_suspends(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository, (StepType.REQUEST_MANUAL_REVIEW, StepType.DETECT_CHAIN)
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.SUSPENDED
    assert handlers[StepType.DETECT_CHAIN].calls == 0


def test_cancel_before_start(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    cancelled = service.cancel_execution(execution.execution_id, "user stop")
    assert cancelled.status is ExecutionStatus.CANCELLED
    assert service.run_execution(execution.execution_id).success is False


def test_cancel_during_step_prevents_next_and_preserves_existing(
    repository: CaseRepository,
) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (StepType.DETECT_CHAIN, StepType.BUILD_GRAPH, StepType.RUN_INVESTIGATION_FEATURES),
        behavior={StepType.BUILD_GRAPH: "cancel"},
    )
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.CANCELLED
    assert len(result.artifacts) == 1
    assert handlers[StepType.RUN_INVESTIGATION_FEATURES].calls == 0
    assert any(item.event_type is EventType.EXECUTION_CANCELLED for item in service.get_execution_events(result.execution.execution_id))


def test_checkpoint_save_load_and_redaction(repository: CaseRepository) -> None:
    case = repository.create("Case")
    state = ExecutionStateService(repository)
    execution = CaseExecution(
        execution_id="execution_" + "e" * 32,
        case_id=case.case_id,
        plan_id="plan",
        plan_version=1,
    )
    state.create_layout(execution)
    checkpoint = ExecutionCheckpoint(
        execution_id=execution.execution_id,
        step_id="step_x",
        checkpoint_type="cursor",
        state={"api_key": "secret"},
        safe_metadata={"Authorization": "Bearer secret-value"},
    )
    saved = state.save_checkpoint(execution, checkpoint)
    assert saved.state["api_key"] == "[REDACTED]"
    assert state.load_checkpoint(execution, "step_x") == saved


def test_resume_skips_completed_and_retries_cancelled(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (StepType.DETECT_CHAIN, StepType.BUILD_GRAPH),
        behavior={StepType.BUILD_GRAPH: "cancel"},
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    first = service.run_execution(execution.execution_id).execution
    handlers[StepType.BUILD_GRAPH].behavior = "success"
    resumed = service.resume_execution(first.execution_id).execution
    assert resumed.status is ExecutionStatus.COMPLETED
    assert handlers[StepType.DETECT_CHAIN].calls == 1
    assert handlers[StepType.BUILD_GRAPH].calls == 2
    assert resumed.resume_count == 1


def test_resume_plan_version_mismatch(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(
        repository, (StepType.BUILD_GRAPH,), behavior={StepType.BUILD_GRAPH: "failure"}
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    changed = plan.model_copy(update={"plan_version": 2})
    save_plan(repository, changed)
    with pytest.raises(ExecutionGateError, match="version mismatch"):
        service.resume_execution(execution.execution_id)


def test_resume_artifact_hash_mismatch(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(
        repository,
        (StepType.DETECT_CHAIN, StepType.BUILD_GRAPH),
        behavior={StepType.BUILD_GRAPH: "failure"},
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    result = service.run_execution(execution.execution_id).execution
    artifact = result.artifacts[0]
    path = repository.workspace(case.case_id).resolve_relative(artifact.relative_path)
    path.chmod(stat.S_IWRITE)
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ResumeNotAllowedError, match="integrity"):
        service.resume_execution(execution.execution_id)


def test_retry_failed_step_and_preserve_artifacts(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository,
        (StepType.DETECT_CHAIN, StepType.BUILD_GRAPH),
        behavior={StepType.BUILD_GRAPH: "failure"},
    )
    execution = service.create_execution(case.case_id, plan.plan_id)
    result = service.run_execution(execution.execution_id).execution
    original_ids = [item.artifact_id for item in result.artifacts]
    handlers[StepType.BUILD_GRAPH].behavior = "success"
    retried = service.retry_step(execution.execution_id, plan.steps[1].step_id)
    assert retried.status is ExecutionStepStatus.COMPLETED
    assert retried.retry_count == 1
    assert original_ids == [item.artifact_id for item in service.get_execution_artifacts(execution.execution_id)[:1]]
    assert service.get_execution(execution.execution_id).status is ExecutionStatus.COMPLETED


def test_retry_completed_rejected(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    with pytest.raises(RetryNotAllowedError, match="Only failed"):
        service.retry_step(execution.execution_id, plan.steps[0].step_id)


def test_retry_non_retryable_and_limit(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(
        repository, (StepType.BUILD_GRAPH,), behavior={StepType.BUILD_GRAPH: "failure"}
    )
    handlers[StepType.BUILD_GRAPH].retry_supported = False
    execution = service.create_execution(case.case_id, plan.plan_id)
    failed = service.run_execution(execution.execution_id).execution
    with pytest.raises(RetryNotAllowedError, match="not retryable"):
        service.retry_step(execution.execution_id, failed.steps[0].step_id)
    state = failed.steps[0].model_copy(update={"retry_count": 3})
    service.state.save(failed.model_copy(update={"steps": [state]}))
    with pytest.raises(RetryNotAllowedError, match="limit"):
        service.retry_step(execution.execution_id, state.step_id)


def test_artifact_missing_empty_and_traversal(repository: CaseRepository) -> None:
    case = repository.create("Case")
    service = ArtifactService(repository.workspace(case.case_id))
    execution_id = "execution_" + "f" * 32
    directory = repository.workspace(case.case_id).resolve_relative(
        f"executions/{execution_id}/artifacts"
    )
    directory.mkdir(parents=True)
    missing = ArtifactCandidate(
        artifact_type=ArtifactType.OTHER,
        relative_path="artifacts/missing",
        source="test",
    )
    with pytest.raises(ArtifactValidationError, match="does not exist"):
        service.register(execution_id=execution_id, step_id="step", candidate=missing)
    (directory / "empty").write_bytes(b"")
    with pytest.raises(ArtifactValidationError, match="cannot be empty"):
        service.register(
            execution_id=execution_id,
            step_id="step",
            candidate=missing.model_copy(update={"relative_path": "artifacts/empty"}),
        )
    with pytest.raises(ArtifactValidationError, match="escapes"):
        service.register(
            execution_id=execution_id,
            step_id="step",
            candidate=missing.model_copy(update={"relative_path": "../../outside"}),
        )


def test_artifact_hash_relative_path_and_verification(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    artifact = service.run_execution(execution.execution_id).artifacts[0]
    assert not Path(artifact.relative_path).is_absolute()
    assert len(artifact.sha256) == 64
    assert ArtifactService(repository.workspace(case.case_id)).verify(artifact)


def test_expected_artifact_contract_failure(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(repository)
    handlers[StepType.DETECT_CHAIN].expected_artifacts = ("analysis_result",)
    result = service.run_execution(
        service.create_execution(case.case_id, plan.plan_id).execution_id
    )
    assert result.execution.status is ExecutionStatus.PARTIAL
    assert "Expected artifacts missing" in result.execution.failures[0].safe_message


def test_running_cancel_notifies_handler(repository: CaseRepository) -> None:
    case, plan, service, handlers = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    running = execution.model_copy(
        update={
            "status": ExecutionStatus.RUNNING,
            "current_step_id": plan.steps[0].step_id,
        }
    )
    service.state.save(running)
    service.cancel_execution(execution.execution_id, "stop")
    assert handlers[StepType.DETECT_CHAIN].cancel_calls == 1


def test_checkpoint_step_id_cannot_escape_directory(repository: CaseRepository) -> None:
    case = repository.create("Case")
    state = ExecutionStateService(repository)
    execution = CaseExecution(
        execution_id="execution_" + "1" * 32,
        case_id=case.case_id,
        plan_id="plan",
        plan_version=1,
    )
    state.create_layout(execution)
    checkpoint = ExecutionCheckpoint(
        execution_id=execution.execution_id,
        step_id="../../outside",
        checkpoint_type="cursor",
    )
    state.save_checkpoint(execution, checkpoint)
    assert state.load_checkpoint(execution, "../../outside") is not None
    assert not (repository.workspace(case.case_id).path / "outside.json").exists()


def test_execution_log_redacts_secret_and_absolute_path(
    repository: CaseRepository,
) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.state.append_log(
        execution,
        step_id=None,
        level="ERROR",
        message=(
            r"Bearer super-secret-token at C:\Users\private\source.csv "
            "https://user:password@example.test/path?api_key=query-secret"
        ),
        safe_details={"api_key": "secret"},
    )
    content = (
        service.state.execution_dir(case.case_id, execution.execution_id)
        / "logs"
        / "execution.jsonl"
    ).read_text(encoding="utf-8")
    assert "super-secret-token" not in content
    assert r"C:\Users" not in content
    assert '"api_key": "secret"' not in content
    assert "user:password" not in content
    assert "query-secret" not in content


def test_atomic_files_and_append_only_events(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    directory = service.state.execution_dir(case.case_id, execution.execution_id)
    assert not list(directory.rglob("*.tmp"))
    first = (directory / "events.jsonl").read_text(encoding="utf-8")
    service.state.append_log(
        service.get_execution(execution.execution_id),
        step_id=None,
        level="INFO",
        message="done",
    )
    assert (directory / "events.jsonl").read_text(encoding="utf-8") == first


def test_public_service_get_list_events_artifacts(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)
    service.run_execution(execution.execution_id)
    assert service.get_execution(execution.execution_id).execution_id == execution.execution_id
    assert service.list_executions(case.case_id)[0].execution_id == execution.execution_id
    assert service.get_execution_events(execution.execution_id)
    assert service.get_execution_artifacts(execution.execution_id)


def test_event_callback_failure_does_not_fail_execution(repository: CaseRepository) -> None:
    case, plan, service, _ = build_service(repository)
    execution = service.create_execution(case.case_id, plan.plan_id)

    def broken_callback(event):
        raise RuntimeError("observer failure")

    result = service.run_execution(execution.execution_id, broken_callback)
    assert result.execution.status is ExecutionStatus.COMPLETED
    log = (
        service.state.execution_dir(case.case_id, execution.execution_id)
        / "logs"
        / "execution.jsonl"
    ).read_text(encoding="utf-8")
    assert "observer failed" in log


def test_case_v2_migration_adds_execution_summary_fields() -> None:
    from crypto_investigator.cases import migrate_case_payload

    migrated = migrate_case_payload(
        {
            "schema_version": 2,
            "case_id": new_case_id(),
            "title": "Legacy",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "unknown": "keep",
        }
    )
    assert migrated["schema_version"] == 3
    assert migrated["executions"] == []
    assert migrated["unknown"] == "keep"
