from __future__ import annotations

from crypto_investigator.application.execution_models import FailureKind
from crypto_investigator.planner.models import StepType

FATAL_STEPS = {
    StepType.VALIDATE_CASE_INPUTS,
    StepType.IMPORT_TRANSACTIONS,
}
PARTIAL_STEPS = {
    StepType.ANALYZE_ADDRESS,
    StepType.ANALYZE_TRANSACTION,
    StepType.GENERATE_REPORT,
}
RECOVERABLE_STEPS = {
    StepType.BUILD_GRAPH,
    StepType.RUN_INVESTIGATION_FEATURES,
    StepType.GENERATE_NARRATIVE,
    StepType.EXPORT_EVIDENCE_MANIFEST,
    StepType.APPLY_LOCAL_LABELS,
}


def failure_kind_for(step_type: StepType) -> FailureKind:
    if step_type in FATAL_STEPS:
        return FailureKind.FATAL
    if step_type in PARTIAL_STEPS:
        return FailureKind.PARTIAL
    if step_type in RECOVERABLE_STEPS:
        return FailureKind.RECOVERABLE
    if step_type is StepType.UNSUPPORTED_RECOMMENDED_STEP:
        return FailureKind.UNSUPPORTED
    return FailureKind.RECOVERABLE
