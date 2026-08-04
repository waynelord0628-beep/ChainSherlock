from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from crypto_investigator.cases.errors import InvalidCaseIdError, UnsafeCasePathError

_SAFE_CASE_ID = re.compile(r"^case_[0-9a-f]{32}$")


def new_case_id() -> str:
    return f"case_{uuid4().hex}"


def validate_case_id(case_id: str) -> str:
    if not _SAFE_CASE_ID.fullmatch(case_id):
        raise InvalidCaseIdError(
            "case_id must use the generated 'case_' plus 32 lowercase hex characters format"
        )
    return case_id


@dataclass(frozen=True, slots=True)
class CaseWorkspace:
    root: Path
    case_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())
        validate_case_id(self.case_id)

    @property
    def path(self) -> Path:
        return self.root / self.case_id

    @property
    def case_file(self) -> Path:
        return self.path / "case.json"

    @property
    def evidence_dir(self) -> Path:
        return self.path / "evidence"

    @property
    def audit_file(self) -> Path:
        return self.path / "audit" / "audit.jsonl"

    def create(self) -> None:
        self.evidence_dir.mkdir(parents=True, exist_ok=False)
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def resolve_relative(self, relative_path: str | Path) -> Path:
        candidate_value = Path(relative_path)
        if candidate_value.is_absolute():
            raise UnsafeCasePathError("absolute paths are not allowed in a case workspace")
        candidate = (self.path / candidate_value).resolve()
        try:
            candidate.relative_to(self.path.resolve())
        except ValueError as exc:
            raise UnsafeCasePathError("path escapes the case workspace") from exc
        return candidate
