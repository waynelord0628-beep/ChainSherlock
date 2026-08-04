from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PackageFileEntry(BaseModel):
    relative_path: str
    sha256: str
    size: int
    artifact_type: str


class CasePackageManifest(BaseModel):
    package_version: int = 1
    export_mode: str
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_case_id: str
    case_schema_version: int
    file_count: int
    total_size: int
    files: list[PackageFileEntry]
    included_evidence: bool
    excluded_categories: list[str] = Field(default_factory=list)
    deidentified: bool = False
    tool_version: str
    manifest_sha256: str
