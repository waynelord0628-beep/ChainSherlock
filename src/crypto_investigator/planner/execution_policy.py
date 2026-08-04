from crypto_investigator.planner.errors import UnconfirmedPlanError
from crypto_investigator.planner.models import InvestigationPlan, StepStatus, StepType


def executable_steps(plan: InvestigationPlan):
    if not plan.is_confirmed:
        raise UnconfirmedPlanError("Plan must be confirmed before execution")
    return tuple(
        step
        for step in plan.steps
        if step.enabled
        and step.status in {StepStatus.APPROVED, StepStatus.PENDING}
        and step.step_type is not StepType.UNSUPPORTED_RECOMMENDED_STEP
    )
