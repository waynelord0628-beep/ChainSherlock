from __future__ import annotations

from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_models import StepExecutionResult
from crypto_investigator.application.execution_registry import ExecutionRegistry
from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.planner.models import PlanStep


class StepDispatcher:
    def __init__(self, registry: ExecutionRegistry) -> None:
        self.registry = registry

    def dispatch(
        self, case: CaseRecord, step: PlanStep, context: ExecutionContext
    ) -> StepExecutionResult:
        handler = self.registry.get(step.step_type)
        handler.validate_input(case, step, context)
        context.cancellation_token.raise_if_cancelled()
        result = handler.execute(
            case, step, context, context.cancellation_token
        )
        context.cancellation_token.raise_if_cancelled()
        return result

    def cancel(self, step: PlanStep, context: ExecutionContext) -> None:
        self.registry.get(step.step_type).cancel(context)
