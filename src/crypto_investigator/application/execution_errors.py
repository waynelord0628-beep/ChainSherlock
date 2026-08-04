class ExecutionServiceError(Exception):
    """Base case execution error."""


class ExecutionGateError(ExecutionServiceError):
    """Raised when a plan or case cannot enter execution."""


class ExecutionNotFoundError(ExecutionServiceError):
    """Raised when an execution cannot be found."""


class UnknownStepHandlerError(ExecutionServiceError):
    """Raised when no handler is registered for a step type."""


class ArtifactValidationError(ExecutionServiceError):
    """Raised when an artifact is unsafe, missing, or incomplete."""


class ExecutionCancelledError(ExecutionServiceError):
    """Cooperative cancellation boundary."""


class RetryNotAllowedError(ExecutionServiceError):
    """Raised when a step cannot be retried."""


class ResumeNotAllowedError(ExecutionServiceError):
    """Raised when an execution cannot be resumed safely."""
