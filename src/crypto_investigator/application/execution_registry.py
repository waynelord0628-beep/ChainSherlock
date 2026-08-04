from __future__ import annotations

from typing import Protocol

from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_models import (
    CancellationToken,
    StepExecutionResult,
)
from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.planner.models import PlanStep, StepType


class StepHandler(Protocol):
    supported_step_type: StepType
    resume_supported: bool
    retry_supported: bool
    expected_artifacts: tuple[str, ...]

    def validate_input(
        self, case: CaseRecord, step: PlanStep, context: ExecutionContext
    ) -> None: ...

    def execute(
        self,
        case: CaseRecord,
        step: PlanStep,
        context: ExecutionContext,
        cancellation_token: CancellationToken,
    ) -> StepExecutionResult: ...

    def cancel(self, context: ExecutionContext) -> None: ...


class ExecutionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[StepType, StepHandler] = {}

    def register(self, handler: StepHandler) -> None:
        step_type = handler.supported_step_type
        if step_type in self._handlers:
            raise ValueError(f"Handler already registered: {step_type.value}")
        self._handlers[step_type] = handler

    def get(self, step_type: StepType) -> StepHandler:
        from crypto_investigator.application.execution_errors import UnknownStepHandlerError

        try:
            return self._handlers[step_type]
        except KeyError as exc:
            raise UnknownStepHandlerError(
                f"No handler registered for step type: {step_type.value}"
            ) from exc

    def step_types(self) -> tuple[StepType, ...]:
        return tuple(sorted(self._handlers, key=lambda item: item.value))
