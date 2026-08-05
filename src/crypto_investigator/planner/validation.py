from __future__ import annotations

from collections import Counter

from crypto_investigator.planner.errors import PlanValidationError
from crypto_investigator.planner.models import InvestigationPlan, StepType


def plan_validation_issues(plan: InvestigationPlan) -> tuple[str, ...]:
    issues: list[str] = []
    ids = [step.step_id for step in plan.steps]
    duplicate_ids = sorted(item for item, count in Counter(ids).items() if count > 1)
    issues.extend(f"duplicate step_id: {item}" for item in duplicate_ids)

    orders = [step.order for step in plan.steps]
    duplicate_orders = sorted(item for item, count in Counter(orders).items() if count > 1)
    issues.extend(f"duplicate order: {item}" for item in duplicate_orders)
    if orders and sorted(orders) != list(range(1, len(orders) + 1)):
        issues.append("step order must be contiguous from 1")

    by_id = {step.step_id: step for step in plan.steps}
    for step in plan.steps:
        for prerequisite in step.prerequisites:
            dependency = by_id.get(prerequisite)
            if dependency is None:
                issues.append(f"missing prerequisite {prerequisite} for {step.step_id}")
                continue
            if dependency.order >= step.order:
                issues.append(f"prerequisite order invalid for {step.step_id}: {prerequisite}")
            if step.enabled and not dependency.enabled:
                issues.append(f"disabled prerequisite {prerequisite} for {step.step_id}")
        if step.step_type in {
            StepType.ANALYZE_ADDRESS,
            StepType.ANALYZE_TRANSACTION,
            StepType.TRACE_FUNDS,
        } and (not step.target_ids or step.chain is None):
            issues.append(f"missing target or chain for {step.step_id}")
        if step.step_type is StepType.GENERATE_NARRATIVE:
            if not step.requires_confirmation:
                issues.append(f"AI narrative step requires confirmation: {step.step_id}")
            dependencies = {by_id[item].step_type for item in step.prerequisites if item in by_id}
            if StepType.RUN_INVESTIGATION_FEATURES not in dependencies:
                issues.append(f"narrative requires investigation result: {step.step_id}")
        if step.step_type is StepType.GENERATE_REPORT:
            dependencies = {by_id[item].step_type for item in step.prerequisites if item in by_id}
            required = {
                StepType.RUN_INVESTIGATION_FEATURES,
                StepType.BUILD_GRAPH,
                StepType.EXPORT_EVIDENCE_MANIFEST,
            }
            if not required.issubset(dependencies):
                issues.append(f"report dependencies incomplete: {step.step_id}")
        if step.step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP and step.enabled:
            issues.append(f"unsupported step cannot be executable: {step.step_id}")

        for parameter, limit_name in (
            ("max_pages", "max_pages"),
            ("max_records", "max_records"),
        ):
            if parameter not in step.parameters:
                continue
            value = step.parameters[parameter]
            limit = plan.settings_snapshot.get(limit_name)
            if not isinstance(value, int) or value < 1:
                issues.append(f"{parameter} must be a positive integer: {step.step_id}")
            elif isinstance(limit, int) and value > limit:
                issues.append(f"{parameter} exceeds configured limit: {step.step_id}")

    graph = {step.step_id: tuple(step.prerequisites) for step in plan.steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph.get(node, ()) if child in graph):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(visit(node) for node in graph):
        issues.append("cyclic step dependency")
    return tuple(dict.fromkeys(issues))


def validate_plan(plan: InvestigationPlan) -> InvestigationPlan:
    issues = plan_validation_issues(plan)
    if issues:
        raise PlanValidationError(issues)
    return plan
