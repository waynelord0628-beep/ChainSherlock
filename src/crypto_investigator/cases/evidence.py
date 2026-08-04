from __future__ import annotations

import hashlib
import mimetypes
import os
import stat
import tempfile
from pathlib import Path
from uuid import uuid4

from crypto_investigator.cases.audit import AuditLog
from crypto_investigator.cases.errors import EvidenceIntegrityError
from crypto_investigator.cases.models import EvidenceRecord, utc_now
from crypto_investigator.cases.repository import CaseRepository

_KNOWN_FILE_TYPES = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class EvidenceManager:
    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def import_file(
        self,
        case_id: str,
        source: Path | str,
        *,
        description: str | None = None,
        actor: str = "local-user",
    ) -> EvidenceRecord:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        record = self.repository.load(case_id)
        workspace = self.repository.workspace(case_id)
        evidence_id = f"evidence_{uuid4().hex}"
        safe_suffix = source_path.suffix.lower()[:20]
        relative_path = f"evidence/{evidence_id}{safe_suffix}"
        destination = workspace.resolve_relative(relative_path)

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{evidence_id}.", suffix=".tmp", dir=workspace.evidence_dir
        )
        digest = hashlib.sha256()
        size = 0
        try:
            with source_path.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
                for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
                    output_stream.write(chunk)
                output_stream.flush()
                os.fsync(output_stream.fileno())
            os.replace(temporary_name, destination)
            destination.chmod(stat.S_IREAD)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

        file_type = _KNOWN_FILE_TYPES.get(safe_suffix)
        if file_type is None:
            file_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        evidence = EvidenceRecord(
            evidence_id=evidence_id,
            relative_path=relative_path,
            original_filename=source_path.name,
            sha256=digest.hexdigest(),
            size=size,
            file_type=file_type,
            imported_at=utc_now(),
            description=description,
        )
        try:
            self.repository.save(
                record.model_copy(update={"evidence": [*record.evidence, evidence]})
            )
            AuditLog(workspace).append(
                action="evidence.imported",
                object_type="evidence",
                object_id=evidence_id,
                description="Evidence imported",
                actor=actor,
                metadata={
                    "relative_path": relative_path,
                    "sha256": evidence.sha256,
                    "size": size,
                    "file_type": file_type,
                },
            )
        except Exception:
            destination.chmod(stat.S_IWRITE)
            destination.unlink(missing_ok=True)
            raise
        return evidence

    def path_for(self, case_id: str, evidence_id: str) -> Path:
        record = self.repository.load(case_id)
        evidence = next(
            (item for item in record.evidence if item.evidence_id == evidence_id),
            None,
        )
        if evidence is None:
            raise KeyError(evidence_id)
        return self.repository.workspace(case_id).resolve_relative(evidence.relative_path)

    def verify(self, case_id: str, evidence_id: str) -> bool:
        record = self.repository.load(case_id)
        evidence = next(
            (item for item in record.evidence if item.evidence_id == evidence_id),
            None,
        )
        if evidence is None:
            raise KeyError(evidence_id)
        path = self.repository.workspace(case_id).resolve_relative(evidence.relative_path)
        if not path.is_file() or path.stat().st_size != evidence.size:
            return False
        return sha256_file(path) == evidence.sha256

    def assert_integrity(self, case_id: str, evidence_id: str) -> None:
        if not self.verify(case_id, evidence_id):
            raise EvidenceIntegrityError(f"Evidence integrity check failed: {evidence_id}")
