from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from crypto_investigator.cases import AuditLog, CaseRepository
from crypto_investigator.planner.engine import DeterministicPlanner
from crypto_investigator.planner.goals import InvestigationGoal
from crypto_investigator.planner.models import (
    InvestigationPlan,
    PlanConfirmation,
    StepStatus,
)
from crypto_investigator.planner.validation import validate_plan


class PlanningService:
    """Persists public planner state and audit events without executing steps."""

    def __init__(self, repository: CaseRepository, planner: DeterministicPlanner) -> None:
        self.repository = repository
        self.planner = planner

    def add_goal(self, case_id: str, goal: InvestigationGoal) -> InvestigationGoal:
        case = self.repository.load(case_id)
        goals = [*case.goals, goal.model_dump(mode="json")]
        self.repository.save(case.model_copy(update={"goals": goals}))
        AuditLog(self.repository.workspace(case_id)).append(
            action="goal.created",
            object_type="goal",
            object_id=goal.goal_id,
            description="Investigation goal created",
            actor=goal.created_by,
            metadata={"goal_type": goal.goal_type.value},
        )
        return goal

    def create_plan(self, case_id: str) -> InvestigationPlan:
        case = self.repository.load(case_id)
        goals = [InvestigationGoal.model_validate(item) for item in case.goals]
        plan = self.planner.create_plan(case, goals)
        self._save_plan(case_id, plan)
        AuditLog(self.repository.workspace(case_id)).append(
            action="plan_created",
            object_type="plan",
            object_id=plan.plan_id,
            description="Deterministic investigation plan created",
            metadata={"plan_version": plan.plan_version, "step_count": len(plan.steps)},
        )
        return plan

    def modify_plan(
        self,
        plan: InvestigationPlan,
        *,
        enabled: Mapping[str, bool] | None = None,
        parameters: Mapping[str, Mapping[str, Any]] | None = None,
        actor: str = "local-user",
    ) -> InvestigationPlan:
        enabled = enabled or {}
        parameters = parameters or {}
        steps = []
        for step in plan.steps:
            changes: dict[str, Any] = {}
            if step.step_id in enabled:
                changes["enabled"] = enabled[step.step_id]
                if not enabled[step.step_id]:
                    changes["status"] = StepStatus.SKIPPED
                elif step.status is StepStatus.SKIPPED:
                    changes["status"] = StepStatus.PROPOSED
            if step.step_id in parameters:
                changes["parameters"] = {**step.parameters, **parameters[step.step_id]}
            steps.append(step.model_copy(update=changes))
        modified = plan.model_copy(
            update={
                "steps": steps,
                "plan_version": plan.plan_version + 1,
                "confirmed_at": None,
                "confirmed_by": None,
            }
        )
        validate_plan(modified)
        self._save_plan(plan.case_id, modified)
        AuditLog(self.repository.workspace(plan.case_id)).append(
            action="plan_modified",
            object_type="plan",
            object_id=plan.plan_id,
            description="Investigation plan modified",
            actor=actor,
            metadata={"plan_version": modified.plan_version},
        )
        return modified

    def confirm_plan(
        self,
        plan: InvestigationPlan,
        confirmation: PlanConfirmation,
    ) -> InvestigationPlan:
        if not confirmation.confirmed:
            return plan
        steps = [
            step.model_copy(
                update={
                    "status": (
                        StepStatus.APPROVED
                        if step.enabled and step.status is StepStatus.PROPOSED
                        else step.status
                    )
                }
            )
            for step in plan.steps
        ]
        confirmed = plan.model_copy(
            update={
                "steps": steps,
                "confirmed_at": confirmation.confirmed_at,
                "confirmed_by": confirmation.confirmed_by,
                # The deterministic planner snapshot is already allowlisted and
                # secret-free. Caller-provided confirmation metadata must not
                # overwrite persisted configuration.
                "settings_snapshot": dict(plan.settings_snapshot),
            }
        )
        validate_plan(confirmed)
        self._save_plan(plan.case_id, confirmed)
        AuditLog(self.repository.workspace(plan.case_id)).append(
            action="plan_confirmed",
            object_type="plan",
            object_id=plan.plan_id,
            description="Investigation plan confirmed by user",
            actor=confirmation.confirmed_by,
            metadata={
                "plan_version": confirmed.plan_version,
                "enabled_step_ids": [
                    step.step_id for step in confirmed.steps if step.enabled
                ],
            },
        )
        return confirmed

    def _save_plan(self, case_id: str, plan: InvestigationPlan) -> None:
        case = self.repository.load(case_id)
        serialized = plan.model_dump(mode="json")
        plans = [
            item for item in case.plans if item.get("plan_id") != plan.plan_id
        ]
        plans.append(serialized)
        self.repository.save(case.model_copy(update={"plans": plans}))
