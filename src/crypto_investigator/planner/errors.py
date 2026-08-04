class PlannerError(Exception):
    """Base investigation planner error."""


class PlanValidationError(PlannerError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issues))


class UnconfirmedPlanError(PlannerError):
    """Raised when execution is requested before user confirmation."""


class NoExecutableClueError(PlannerError):
    """Raised when no supported target or structured evidence is available."""
