from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from crypto_investigator.application.execution_errors import ExecutionNotFoundError
from crypto_investigator.application.execution_events import ExecutionEvent
from crypto_investigator.application.execution_models import (
    CaseExecution,
    ExecutionCheckpoint,
)
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.storage import atomic_write_json

_SAFE_EXECUTION_ID = re.compile(r"^execution_[0-9a-f]{32}$")


class ExecutionStateService:
    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def execution_dir(self, case_id: str, execution_id: str) -> Path:
        if not _SAFE_EXECUTION_ID.fullmatch(execution_id):
            raise ExecutionNotFoundError(execution_id)
        return self.repository.workspace(case_id).resolve_relative(
            Path("executions") / execution_id
        )

    def create_layout(self, execution: CaseExecution) -> Path:
        directory = self.execution_dir(execution.case_id, execution.execution_id)
        directory.mkdir(parents=True, exist_ok=False)
        for name in ("steps", "artifacts", "logs", "checkpoints"):
            (directory / name).mkdir()
        self.save(execution)
        return directory

    def save(self, execution: CaseExecution) -> None:
        atomic_write_json(
            self.execution_dir(execution.case_id, execution.execution_id) / "execution.json",
            execution.model_dump(mode="json"),
        )

    def save_step(self, execution: CaseExecution, step) -> Path:
        path = self.step_dir(execution, step.order, step.step_id) / "step.json"
        atomic_write_json(path, step.model_dump(mode="json"))
        return path

    def step_dir(self, execution: CaseExecution, order: int, step_id: str) -> Path:
        safe_step = re.sub(r"[^A-Za-z0-9_.-]", "_", step_id)
        path = self.execution_dir(execution.case_id, execution.execution_id) / "steps" / f"{order:03d}_{safe_step}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def load(self, execution_id: str, case_id: str | None = None) -> CaseExecution:
        if case_id is not None:
            candidates = [
                self.execution_dir(case_id, execution_id) / "execution.json"
            ]
        else:
            if not _SAFE_EXECUTION_ID.fullmatch(execution_id):
                raise ExecutionNotFoundError(execution_id)
            candidates = list(
                self.repository.root.glob(
                    f"case_*/executions/{execution_id}/execution.json"
                )
            )
        if len(candidates) != 1 or not candidates[0].is_file():
            raise ExecutionNotFoundError(execution_id)
        return CaseExecution.model_validate_json(
            candidates[0].read_text(encoding="utf-8")
        )

    def append_event(self, event: ExecutionEvent) -> None:
        path = self.execution_dir(event.case_id, event.execution_id) / "events.jsonl"
        safe = event.model_copy(
            update={
                "message": redact_sensitive(event.message),
                "safe_details": redact_sensitive(event.safe_details),
            }
        )
        encoded = (safe.model_dump_json() + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def events(self, execution: CaseExecution) -> tuple[ExecutionEvent, ...]:
        path = self.execution_dir(execution.case_id, execution.execution_id) / "events.jsonl"
        if not path.exists():
            return ()
        return tuple(
            ExecutionEvent.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def save_checkpoint(
        self, execution: CaseExecution, checkpoint: ExecutionCheckpoint
    ) -> ExecutionCheckpoint:
        safe = ExecutionCheckpoint.model_validate(
            redact_sensitive(checkpoint.model_dump(mode="json"))
        )
        safe_step_id = re.sub(
            r"[^A-Za-z0-9_.-]", "_", str(redact_sensitive(safe.step_id))
        )
        path = (
            self.execution_dir(execution.case_id, execution.execution_id)
            / "checkpoints"
            / f"{safe_step_id}.json"
        )
        atomic_write_json(path, safe.model_dump(mode="json"))
        return safe

    def load_checkpoint(
        self, execution: CaseExecution, step_id: str
    ) -> ExecutionCheckpoint | None:
        safe_step_id = re.sub(
            r"[^A-Za-z0-9_.-]", "_", str(redact_sensitive(step_id))
        )
        path = (
            self.execution_dir(execution.case_id, execution.execution_id)
            / "checkpoints"
            / f"{safe_step_id}.json"
        )
        if not path.is_file():
            return None
        return ExecutionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))

    def append_log(
        self,
        execution: CaseExecution,
        *,
        step_id: str | None,
        level: str,
        message: str,
        safe_details: dict[str, Any] | None = None,
    ) -> None:
        payload = redact_sensitive(
            {
                "timestamp": execution.started_at or execution.created_at,
                "execution_id": execution.execution_id,
                "step_id": step_id,
                "level": level,
                "message": message,
                "safe_details": safe_details or {},
            }
        )
        path = self.execution_dir(execution.case_id, execution.execution_id) / "logs" / "execution.jsonl"
        encoded = (json.dumps(payload, default=str, ensure_ascii=False) + "\n").encode()
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
