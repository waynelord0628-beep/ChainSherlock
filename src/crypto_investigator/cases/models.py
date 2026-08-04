from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


CURRENT_CASE_SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CaseStatus(StrEnum):
    OPEN = "open"
    ARCHIVED = "archived"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    evidence_id: str
    relative_path: str
    original_filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)
    file_type: str
    imported_at: datetime
    description: str | None = None

    @field_validator("imported_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("imported_at must be timezone-aware")
        return value

    @field_validator("relative_path")
    @classmethod
    def require_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("evidence path must be a safe relative path")
        return normalized


class CaseRecord(BaseModel):
    """Public, forward-compatible persistence model for a case."""

    model_config = ConfigDict(extra="allow")

    schema_version: int = CURRENT_CASE_SCHEMA_VERSION
    case_id: str = Field(pattern=r"^case_[0-9a-f]{32}$")
    title: str
    description: str = ""
    status: CaseStatus = CaseStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("case timestamps must be timezone-aware")
        return value


class CaseAuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utc_now)
    action: str
    object_type: str
    object_id: str
    description: str
    actor: str = "local-user"
    previous_hash: str | None = None
    entry_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("audit timestamp must be timezone-aware")
        return value
