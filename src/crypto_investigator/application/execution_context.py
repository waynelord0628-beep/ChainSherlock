from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from crypto_investigator.application.execution_models import (
    CancellationToken,
    CaseExecution,
)
from crypto_investigator.cases.models import CaseRecord


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    case: CaseRecord
    execution: CaseExecution
    execution_dir: Path
    step_dir: Path
    artifacts_dir: Path
    checkpoints_dir: Path
    cancellation_token: CancellationToken
