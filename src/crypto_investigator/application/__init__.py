from crypto_investigator.application.execution_context import ExecutionContext
from crypto_investigator.application.execution_events import EventType, ExecutionEvent
from crypto_investigator.application.execution_models import (
    ArtifactCandidate,
    ArtifactType,
    CancellationToken,
    CaseExecution,
    CaseExecutionResult,
    Completeness,
    ExecutionArtifact,
    ExecutionCheckpoint,
    ExecutionFailure,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionWarning,
    FailureKind,
    StepExecution,
    StepExecutionResult,
)
from crypto_investigator.application.execution_registry import (
    ExecutionRegistry,
    StepHandler,
)
from crypto_investigator.application.execution_service import CaseExecutionService
from crypto_investigator.application.offline_handlers import (
    create_offline_execution_registry,
)
from crypto_investigator.application.case_result_service import CaseResultService
from crypto_investigator.application.case_report_service import CaseReportService
from crypto_investigator.application.case_package_service import CasePackageService

__all__ = [
    "ArtifactCandidate",
    "ArtifactType",
    "CancellationToken",
    "CaseExecution",
    "CaseExecutionResult",
    "CaseExecutionService",
    "create_offline_execution_registry",
    "create_desktop_execution_registry",
    "Completeness",
    "EventType",
    "ExecutionArtifact",
    "ExecutionCheckpoint",
    "ExecutionContext",
    "ExecutionEvent",
    "ExecutionFailure",
    "ExecutionRegistry",
    "ExecutionStatus",
    "ExecutionStepStatus",
    "ExecutionWarning",
    "FailureKind",
    "StepExecution",
    "StepExecutionResult",
    "StepHandler",
    "CasePackageService",
    "CaseReportService",
    "CaseResultService",
]


def __getattr__(name: str):
    if name == "create_desktop_execution_registry":
        from crypto_investigator.application.provider_handlers import (
            create_desktop_execution_registry,
        )

        return create_desktop_execution_registry
    raise AttributeError(name)
