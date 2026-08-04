from __future__ import annotations

import json
import stat
from pathlib import Path

from crypto_investigator.application.execution_errors import ArtifactValidationError
from crypto_investigator.application.execution_models import (
    ArtifactCandidate,
    Completeness,
    ExecutionArtifact,
)
from crypto_investigator.cases.audit import redact_sensitive
from crypto_investigator.cases.storage import atomic_write_json
from crypto_investigator.cases.workspace import CaseWorkspace
from crypto_investigator.cases.evidence import sha256_file


class ArtifactService:
    def __init__(self, workspace: CaseWorkspace) -> None:
        self.workspace = workspace

    def register(
        self,
        *,
        execution_id: str,
        step_id: str,
        candidate: ArtifactCandidate,
    ) -> ExecutionArtifact:
        execution_relative = Path("executions") / execution_id
        execution_dir = self.workspace.resolve_relative(execution_relative)
        candidate_path = Path(candidate.relative_path)
        if candidate_path.is_absolute():
            raise ArtifactValidationError("Artifact path must be relative")
        path = (execution_dir / candidate_path).resolve()
        try:
            relative_to_case = path.relative_to(self.workspace.path.resolve())
            path.relative_to(execution_dir.resolve())
        except ValueError as exc:
            raise ArtifactValidationError("Artifact path escapes execution workspace") from exc
        if not path.is_file():
            raise ArtifactValidationError("Artifact file does not exist")
        size = path.stat().st_size
        if size == 0 and candidate.completeness is not Completeness.EMPTY:
            raise ArtifactValidationError("Complete artifact cannot be empty")
        artifact = ExecutionArtifact(
            case_id=self.workspace.case_id,
            execution_id=execution_id,
            step_id=step_id,
            artifact_type=candidate.artifact_type,
            relative_path=relative_to_case.as_posix(),
            sha256=sha256_file(path),
            size=size,
            source=str(redact_sensitive(candidate.source)),
            completeness=candidate.completeness,
            metadata=redact_sensitive(candidate.metadata),
        )
        path.chmod(stat.S_IREAD)
        return artifact

    def verify(self, artifact: ExecutionArtifact) -> bool:
        path = self.workspace.resolve_relative(artifact.relative_path)
        return (
            path.is_file()
            and path.stat().st_size == artifact.size
            and sha256_file(path) == artifact.sha256
        )

    def save_manifest(
        self, execution_id: str, artifacts: list[ExecutionArtifact]
    ) -> Path:
        path = self.workspace.resolve_relative(
            Path("executions") / execution_id / "artifacts" / "manifest.json"
        )
        atomic_write_json(
            path,
            {"artifacts": [item.model_dump(mode="json") for item in artifacts]},
        )
        return path
