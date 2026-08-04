from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from crypto_investigator.cases import AuditLog
from crypto_investigator.cases.migration import migrate_case_payload
from crypto_investigator.cases.models import CaseRecord
from crypto_investigator.cases.package import CasePackageManifest
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.storage import atomic_write_json
from crypto_investigator.cases.workspace import new_case_id


class CasePackageValidationError(ValueError):
    pass


class CasePackageImporter:
    MAX_FILES = 1000
    MAX_FILE_SIZE = 100 * 1024 * 1024
    MAX_TOTAL_SIZE = 500 * 1024 * 1024
    MAX_RATIO = 200

    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def validate(self, package_path: Path) -> CasePackageManifest:
        try:
            with zipfile.ZipFile(package_path) as archive:
                infos = archive.infolist()
                if len(infos) > self.MAX_FILES:
                    raise CasePackageValidationError("Package contains too many files")
                total = 0
                names = set()
                for info in infos:
                    path = PurePosixPath(info.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or ":" in info.filename
                        or "\\" in info.filename
                    ):
                        raise CasePackageValidationError("Unsafe package path")
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise CasePackageValidationError("Symlink entries are forbidden")
                    if info.file_size > self.MAX_FILE_SIZE:
                        raise CasePackageValidationError("Package file exceeds size limit")
                    if (
                        info.compress_size
                        and info.file_size / info.compress_size > self.MAX_RATIO
                    ):
                        raise CasePackageValidationError("Suspicious compression ratio")
                    total += info.file_size
                    names.add(info.filename)
                if total > self.MAX_TOTAL_SIZE:
                    raise CasePackageValidationError("Package total size exceeds limit")
                if "case_package_manifest.json" not in names:
                    raise CasePackageValidationError("Package manifest is missing")
                manifest = CasePackageManifest.model_validate_json(
                    archive.read("case_package_manifest.json")
                )
                base = manifest.model_dump(
                    mode="json", exclude={"manifest_sha256"}
                )
                expected_manifest = hashlib.sha256(
                    json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                if expected_manifest != manifest.manifest_sha256:
                    raise CasePackageValidationError("Manifest hash mismatch")
                by_name = {item.relative_path: item for item in manifest.files}
                if set(by_name) != names - {"case_package_manifest.json"}:
                    raise CasePackageValidationError("Manifest file list mismatch")
                for name, entry in by_name.items():
                    data = archive.read(name)
                    if len(data) != entry.size or hashlib.sha256(data).hexdigest() != entry.sha256:
                        raise CasePackageValidationError(f"File hash mismatch: {name}")
                return manifest
        except (zipfile.BadZipFile, OSError, KeyError, ValueError) as exc:
            if isinstance(exc, CasePackageValidationError):
                raise
            raise CasePackageValidationError("Invalid case package") from exc

    def import_package(self, package_path: Path) -> CaseRecord:
        manifest = self.validate(package_path)
        new_id = new_case_id()
        temporary = Path(
            tempfile.mkdtemp(prefix=".case-import-", dir=self.repository.root)
        )
        destination = self.repository.root / new_id
        try:
            with zipfile.ZipFile(package_path) as archive:
                for entry in manifest.files:
                    target = temporary / PurePosixPath(entry.relative_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry.relative_path) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            case_file = temporary / "case.json"
            if case_file.is_file():
                payload = migrate_case_payload(
                    json.loads(case_file.read_text(encoding="utf-8"))
                )
                original_id = payload.get("case_id")
                payload["case_id"] = new_id
                payload["status"] = "open"
                payload.setdefault("metadata", {})["original_case_id"] = original_id
            else:
                payload = CaseRecord(
                    case_id=new_id,
                    title="Imported case package",
                    metadata={"original_case_id": manifest.source_case_id},
                ).model_dump(mode="json")
            atomic_write_json(case_file, payload)
            (temporary / "evidence").mkdir(exist_ok=True)
            (temporary / "audit").mkdir(exist_ok=True)
            os.replace(temporary, destination)
            record = self.repository.load(new_id)
            AuditLog(self.repository.workspace(new_id)).append(
                action="case_imported",
                object_type="case",
                object_id=new_id,
                description="Case package imported",
                metadata={
                    "original_case_id": record.metadata.get("original_case_id"),
                    "export_mode": manifest.export_mode,
                },
            )
            return record
        except Exception:
            if destination.exists():
                shutil.rmtree(destination)
            raise
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
