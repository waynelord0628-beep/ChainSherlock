from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from crypto_investigator import __version__
from crypto_investigator.cases.deidentification import Deidentifier
from crypto_investigator.cases.package import CasePackageManifest, PackageFileEntry
from crypto_investigator.cases.repository import CaseRepository
from crypto_investigator.cases.results import CaseResult
from crypto_investigator.cases.audit import redact_sensitive

_SECRET_BYTES = (
    b"sk-proj-",
    b"authorization: bearer",
    b"authorization\": \"bearer",
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CasePackageExporter:
    MODES = {"full", "deidentified", "report_only"}

    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def export(
        self,
        case_id: str,
        destination: Path,
        *,
        mode: str,
        case_result: CaseResult,
    ) -> Path:
        if mode not in self.MODES:
            raise ValueError(f"Unsupported package mode: {mode}")
        case = self.repository.load(case_id)
        workspace = self.repository.workspace(case_id)
        files: dict[str, tuple[bytes, str]] = {}
        excluded = [".env", "cache", "credentials", "temporary_files"]
        if mode == "full":
            case_payload = redact_sensitive(
                json.loads(workspace.case_file.read_text(encoding="utf-8"))
            )
            files["case.json"] = (
                json.dumps(case_payload, ensure_ascii=False, indent=2).encode(),
                "case_record",
            )
            if workspace.audit_file.is_file():
                files["audit/audit.jsonl"] = (
                    workspace.audit_file.read_bytes(),
                    "audit_log",
                )
            for evidence in case.evidence:
                path = workspace.resolve_relative(evidence.relative_path)
                data = path.read_bytes() if path.is_file() else b""
                lowered = data.lower()
                if (
                    data
                    and _digest(data) == evidence.sha256
                    and not any(secret in lowered for secret in _SECRET_BYTES)
                ):
                    files[evidence.relative_path] = (data, "source_evidence")
            for execution_summary in case.executions:
                execution_id = execution_summary.get("execution_id")
                execution_file = workspace.resolve_relative(
                    f"executions/{execution_id}/execution.json"
                )
                if execution_file.is_file():
                    payload = json.loads(execution_file.read_text(encoding="utf-8"))
                    for artifact in payload.get("artifacts", []):
                        path = workspace.resolve_relative(artifact["relative_path"])
                        data = path.read_bytes()
                        if _digest(data) == artifact["sha256"] and not any(
                            secret in data.lower() for secret in _SECRET_BYTES
                        ):
                            files[artifact["relative_path"]] = (
                                data,
                                artifact.get("artifact_type", "artifact"),
                            )
        if mode in {"full", "report_only"}:
            report_root = workspace.resolve_relative("reports")
            if report_root.exists():
                for path in sorted(report_root.rglob("*")):
                    if path.is_file() and not path.name.endswith(".tmp"):
                        relative = path.relative_to(workspace.path).as_posix()
                        files[relative] = (path.read_bytes(), "case_report")
        if mode == "deidentified":
            deidentifier = Deidentifier()
            transformed = deidentifier.transform(case_result.model_dump(mode="json"))
            files["case_result.json"] = (
                json.dumps(transformed, ensure_ascii=False, indent=2).encode(),
                "deidentified_case_result",
            )
            files["deidentification_manifest.json"] = (
                json.dumps(deidentifier.manifest(), ensure_ascii=False, indent=2).encode(),
                "deidentification_manifest",
            )
            excluded.extend(["raw_evidence", "execution_artifacts", "audit_log", "reports"])

        entries = [
            PackageFileEntry(
                relative_path=name,
                sha256=_digest(data),
                size=len(data),
                artifact_type=kind,
            )
            for name, (data, kind) in sorted(files.items())
        ]
        source_id = (
            "deidentified_case"
            if mode == "deidentified"
            else case.case_id
        )
        base = {
            "package_version": 1,
            "export_mode": mode,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source_case_id": source_id,
            "case_schema_version": case.schema_version,
            "file_count": len(entries),
            "total_size": sum(item.size for item in entries),
            "files": [item.model_dump(mode="json") for item in entries],
            "included_evidence": mode == "full" and bool(case.evidence),
            "excluded_categories": excluded,
            "deidentified": mode == "deidentified",
            "tool_version": __version__,
        }
        draft = CasePackageManifest(**base, manifest_sha256="")
        canonical = draft.model_dump(mode="json", exclude={"manifest_sha256"})
        manifest_hash = _digest(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        )
        manifest = draft.model_copy(update={"manifest_sha256": manifest_hash})
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix != ".zip":
            destination = destination.with_suffix(".chainsherlock-case.zip")
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, (data, _) in sorted(files.items()):
                    archive.writestr(name, data)
                archive.writestr(
                    "case_package_manifest.json",
                    manifest.model_dump_json(indent=2),
                )
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
