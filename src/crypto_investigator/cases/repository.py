from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from crypto_investigator.cases.errors import (
    CaseAlreadyExistsError,
    CaseNotFoundError,
)
from crypto_investigator.cases.migration import migrate_case_payload
from crypto_investigator.cases.models import CaseRecord, CaseStatus
from crypto_investigator.cases.storage import atomic_write_json
from crypto_investigator.cases.workspace import CaseWorkspace, new_case_id, validate_case_id


class CaseRepository:
    """Filesystem repository whose directory names are opaque safe case IDs."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def workspace(self, case_id: str) -> CaseWorkspace:
        return CaseWorkspace(self.root, validate_case_id(case_id))

    def create(
        self,
        title: str,
        *,
        description: str = "",
        case_id: str | None = None,
    ) -> CaseRecord:
        resolved_id = validate_case_id(case_id) if case_id else new_case_id()
        workspace = self.workspace(resolved_id)
        if workspace.path.exists():
            raise CaseAlreadyExistsError(resolved_id)
        workspace.create()
        record = CaseRecord(case_id=resolved_id, title=title, description=description)
        atomic_write_json(workspace.case_file, record.model_dump(mode="json"))
        from crypto_investigator.cases.audit import AuditLog

        AuditLog(workspace).append(
            action="case.created",
            object_type="case",
            object_id=resolved_id,
            description="Case created",
        )
        return record

    def load(self, case_id: str) -> CaseRecord:
        workspace = self.workspace(case_id)
        if not workspace.case_file.is_file():
            raise CaseNotFoundError(case_id)
        with workspace.case_file.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        return CaseRecord.model_validate(migrate_case_payload(payload))

    def save(self, record: CaseRecord) -> CaseRecord:
        workspace = self.workspace(record.case_id)
        if not workspace.path.is_dir():
            raise CaseNotFoundError(record.case_id)
        updated = record.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        atomic_write_json(workspace.case_file, updated.model_dump(mode="json"))
        return updated

    def list(self, *, include_archived: bool = False) -> tuple[CaseRecord, ...]:
        records: list[CaseRecord] = []
        for case_file in sorted(self.root.glob("case_*/case.json")):
            try:
                record = self.load(case_file.parent.name)
            except (CaseNotFoundError, ValueError, json.JSONDecodeError):
                continue
            if include_archived or record.status != CaseStatus.ARCHIVED:
                records.append(record)
        return tuple(records)

    def archive(self, case_id: str) -> CaseRecord:
        record = self.load(case_id)
        archived = self.save(record.model_copy(update={"status": CaseStatus.ARCHIVED}))
        from crypto_investigator.cases.audit import AuditLog

        AuditLog(self.workspace(case_id)).append(
            action="case.archived",
            object_type="case",
            object_id=case_id,
            description="Case archived",
        )
        return archived

    def duplicate(self, case_id: str, *, title: str | None = None) -> CaseRecord:
        source = self.load(case_id)
        duplicate = self.create(title or f"{source.title} (copy)", description=source.description)
        copied = duplicate.model_copy(
            update={
                "metadata": dict(source.metadata),
                "evidence": [],
            }
        )
        saved = self.save(copied)
        from crypto_investigator.cases.audit import AuditLog

        AuditLog(self.workspace(saved.case_id)).append(
            action="case.duplicated",
            object_type="case",
            object_id=saved.case_id,
            description="Case duplicated",
            metadata={"source_case_id": case_id},
        )
        return saved

    def delete(self, case_id: str) -> Path:
        """Move a case to the repository trash; no permanent deletion is performed."""

        workspace = self.workspace(case_id)
        if not workspace.path.is_dir():
            raise CaseNotFoundError(case_id)
        trash = self.root / ".trash"
        trash.mkdir(exist_ok=True)
        destination = trash / case_id
        if destination.exists():
            destination = trash / f"{case_id}_{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}"
        from crypto_investigator.cases.audit import AuditLog

        AuditLog(workspace).append(
            action="case.deleted",
            object_type="case",
            object_id=case_id,
            description="Case moved to recoverable trash",
        )
        return Path(shutil.move(str(workspace.path), str(destination)))
