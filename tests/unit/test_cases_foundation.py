from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from crypto_investigator.cases import (
    AuditLog,
    CaseRecord,
    CaseRepository,
    CaseStatus,
    CaseWorkspace,
    EvidenceManager,
    migrate_case_payload,
    new_case_id,
)
from crypto_investigator.cases.errors import (
    CaseAlreadyExistsError,
    CaseNotFoundError,
    EvidenceIntegrityError,
    InvalidCaseIdError,
    UnsafeCasePathError,
    UnsupportedCaseSchemaError,
)


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    return CaseRepository(tmp_path / "cases")


@pytest.fixture
def case(repository: CaseRepository) -> CaseRecord:
    return repository.create("測試案件", description="foundation")


def test_generated_case_id_is_opaque_and_safe() -> None:
    case_id = new_case_id()
    assert case_id.startswith("case_")
    assert len(case_id) == 37


@pytest.mark.parametrize(
    "unsafe", ["案件名稱", "../escape", "case_1", "CASE_" + "a" * 32, "case_" + "g" * 32]
)
def test_workspace_rejects_unsafe_case_id(tmp_path: Path, unsafe: str) -> None:
    with pytest.raises(InvalidCaseIdError):
        CaseWorkspace(tmp_path, unsafe)


def test_workspace_directory_does_not_use_title(repository: CaseRepository) -> None:
    record = repository.create("../../案件名稱")
    assert repository.workspace(record.case_id).path.name == record.case_id
    assert "案件名稱" not in str(repository.workspace(record.case_id).path)


def test_workspace_rejects_path_traversal(repository: CaseRepository, case: CaseRecord) -> None:
    with pytest.raises(UnsafeCasePathError):
        repository.workspace(case.case_id).resolve_relative("../../outside")


def test_workspace_rejects_absolute_path(repository: CaseRepository, case: CaseRecord) -> None:
    with pytest.raises(UnsafeCasePathError):
        repository.workspace(case.case_id).resolve_relative(Path.cwd().resolve())


def test_case_model_round_trip_preserves_timezone() -> None:
    record = CaseRecord(case_id=new_case_id(), title="Case")
    restored = CaseRecord.model_validate_json(record.model_dump_json())
    assert restored.created_at.utcoffset() == timezone.utc.utcoffset(None)


def test_case_model_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        CaseRecord(case_id=new_case_id(), title="Case", created_at=datetime(2026, 1, 1))


def test_case_model_rejects_unsafe_case_id() -> None:
    with pytest.raises(ValidationError):
        CaseRecord(case_id="../../case", title="Case")


def test_repository_create_and_load(repository: CaseRepository) -> None:
    created = repository.create("Case")
    assert repository.load(created.case_id).title == "Case"
    entries = list(AuditLog(repository.workspace(created.case_id)).entries())
    assert entries[0].action == "case.created"


def test_repository_create_rejects_duplicate_id(repository: CaseRepository) -> None:
    record = repository.create("Case")
    with pytest.raises(CaseAlreadyExistsError):
        repository.create("Again", case_id=record.case_id)


def test_repository_missing_case(repository: CaseRepository) -> None:
    with pytest.raises(CaseNotFoundError):
        repository.load(new_case_id())


def test_repository_save_updates_timestamp(repository: CaseRepository, case: CaseRecord) -> None:
    updated = repository.save(case.model_copy(update={"title": "Changed"}))
    assert updated.title == "Changed"
    assert updated.updated_at >= case.updated_at


def test_repository_atomic_write_leaves_no_temp_files(
    repository: CaseRepository, case: CaseRecord
) -> None:
    repository.save(case.model_copy(update={"title": "Atomic"}))
    workspace = repository.workspace(case.case_id)
    assert json.loads(workspace.case_file.read_text(encoding="utf-8"))["title"] == "Atomic"
    assert not list(workspace.path.glob(".*.tmp"))


def test_repository_list_excludes_archived(repository: CaseRepository, case: CaseRecord) -> None:
    repository.archive(case.case_id)
    assert repository.list() == ()
    assert repository.list(include_archived=True)[0].status == CaseStatus.ARCHIVED


def test_repository_duplicate_uses_new_safe_id(
    repository: CaseRepository, case: CaseRecord
) -> None:
    duplicate = repository.duplicate(case.case_id)
    assert duplicate.case_id != case.case_id
    assert duplicate.title.endswith("(copy)")


def test_repository_delete_is_recoverable_move(
    repository: CaseRepository, case: CaseRecord
) -> None:
    destination = repository.delete(case.case_id)
    assert destination.parent.name == ".trash"
    assert destination.exists()
    assert "case.deleted" in (destination / "audit" / "audit.jsonl").read_text(encoding="utf-8")
    with pytest.raises(CaseNotFoundError):
        repository.load(case.case_id)


def test_legacy_case_migration_preserves_unknown_fields() -> None:
    payload = {
        "id": new_case_id(),
        "name": "Legacy",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "future_field": {"keep": True},
    }
    migrated = migrate_case_payload(payload)
    record = CaseRecord.model_validate(migrated)
    assert record.title == "Legacy"
    assert record.model_extra == {"id": payload["id"], "name": "Legacy", "future_field": {"keep": True}}


def test_current_schema_unknown_fields_survive_repository_save(
    repository: CaseRepository, case: CaseRecord
) -> None:
    workspace = repository.workspace(case.case_id)
    payload = case.model_dump(mode="json")
    payload["future_extension"] = {"enabled": True}
    workspace.case_file.write_text(json.dumps(payload), encoding="utf-8")
    repository.save(repository.load(case.case_id))
    saved = json.loads(workspace.case_file.read_text(encoding="utf-8"))
    assert saved["future_extension"] == {"enabled": True}


def test_future_schema_is_rejected() -> None:
    with pytest.raises(UnsupportedCaseSchemaError, match="newer"):
        migrate_case_payload({"schema_version": 999})


def test_evidence_import_records_required_metadata(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "statement.csv"
    source.write_bytes("地址,金額\nTABC,1.20\n".encode())
    evidence = EvidenceManager(repository).import_file(case.case_id, source)
    assert evidence.size == source.stat().st_size
    assert len(evidence.sha256) == 64
    assert evidence.file_type == "text/csv"
    assert evidence.imported_at.tzinfo is not None


def test_evidence_record_contains_no_source_absolute_path(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "secret-location.txt"
    source.write_text("evidence", encoding="utf-8")
    EvidenceManager(repository).import_file(case.case_id, source)
    serialized = repository.workspace(case.case_id).case_file.read_text(encoding="utf-8")
    assert str(tmp_path.resolve()) not in serialized
    assert '"relative_path": "evidence/' in serialized


def test_evidence_copy_is_independent_from_source(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    manager = EvidenceManager(repository)
    evidence = manager.import_file(case.case_id, source)
    source.write_bytes(b"changed")
    assert manager.path_for(case.case_id, evidence.evidence_id).read_bytes() == b"original"


def test_evidence_destination_is_read_only(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    manager = EvidenceManager(repository)
    evidence = manager.import_file(case.case_id, source)
    mode = manager.path_for(case.case_id, evidence.evidence_id).stat().st_mode
    assert not mode & stat.S_IWRITE


def test_evidence_integrity_detects_tampering(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"original")
    manager = EvidenceManager(repository)
    evidence = manager.import_file(case.case_id, source)
    stored = manager.path_for(case.case_id, evidence.evidence_id)
    stored.chmod(stat.S_IWRITE)
    stored.write_bytes(b"tampered")
    assert manager.verify(case.case_id, evidence.evidence_id) is False
    with pytest.raises(EvidenceIntegrityError):
        manager.assert_integrity(case.case_id, evidence.evidence_id)


def test_evidence_unknown_id_raises(
    repository: CaseRepository, case: CaseRecord
) -> None:
    with pytest.raises(KeyError):
        EvidenceManager(repository).path_for(case.case_id, "evidence_missing")


def test_import_creates_audit_entry(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    EvidenceManager(repository).import_file(case.case_id, source)
    entries = list(AuditLog(repository.workspace(case.case_id)).entries())
    assert entries[-1].action == "evidence.imported"


def test_audit_log_is_hash_chained(repository: CaseRepository, case: CaseRecord) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    first = audit.append(
        action="case.created", object_type="case", object_id=case.case_id, description="Created"
    )
    second = audit.append(
        action="case.updated", object_type="case", object_id=case.case_id, description="Updated"
    )
    assert second.previous_hash == first.entry_hash
    assert audit.verify() is True


def test_audit_log_detects_tampering(repository: CaseRepository, case: CaseRecord) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    audit.append(
        action="case.created", object_type="case", object_id=case.case_id, description="Created"
    )
    content = audit.path.read_text(encoding="utf-8").replace("Created", "Altered")
    audit.path.write_text(content, encoding="utf-8")
    assert audit.verify() is False


def test_audit_redacts_secrets(repository: CaseRepository, case: CaseRecord) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    audit.append(
        action="case.updated",
        object_type="case",
        object_id=case.case_id,
        description="Updated",
        metadata={"api_key": "sk-secret", "nested": {"Authorization": "Bearer secret"}},
    )
    content = audit.path.read_text(encoding="utf-8")
    assert "sk-secret" not in content
    assert "Bearer secret" not in content
    assert content.count("[REDACTED]") == 2


def test_audit_redacts_secret_values_without_sensitive_key(
    repository: CaseRepository, case: CaseRecord
) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    audit.append(
        action="case.updated",
        object_type="case",
        object_id=case.case_id,
        description="Updated",
        metadata={"message": "request failed with Bearer super-secret-value"},
    )
    content = audit.path.read_text(encoding="utf-8")
    assert "super-secret-value" not in content


def test_audit_string_absolute_path_saves_only_filename(
    repository: CaseRepository, case: CaseRecord
) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    audit.append(
        action="evidence.checked",
        object_type="evidence",
        object_id="evidence_1",
        description="Checked",
        metadata={"path": r"C:\private\source.csv"},
    )
    content = audit.path.read_text(encoding="utf-8")
    assert "C:" not in content
    assert "source.csv" in content


def test_audit_path_metadata_saves_only_filename(
    repository: CaseRepository, case: CaseRecord, tmp_path: Path
) -> None:
    audit = AuditLog(repository.workspace(case.case_id))
    audit.append(
        action="evidence.checked",
        object_type="evidence",
        object_id="evidence_1",
        description="Checked",
        metadata={"path": tmp_path / "private" / "source.csv"},
    )
    content = audit.path.read_text(encoding="utf-8")
    assert str(tmp_path.resolve()) not in content
    assert "source.csv" in content
