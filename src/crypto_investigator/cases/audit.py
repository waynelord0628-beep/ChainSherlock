from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator, Mapping

from crypto_investigator.cases.models import CaseAuditEntry, utc_now
from crypto_investigator.cases.workspace import CaseWorkspace

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "authorization_header",
    "credential",
    "password",
    "secret",
    "token",
}
_SECRET_VALUE = re.compile(r"(?i)(?:bearer\s+|sk-(?:proj-)?)[A-Za-z0-9._-]{8,}")
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def _safe_metadata(value: Any, *, key: str = "") -> Any:
    if key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _safe_metadata(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_metadata(item) for item in value]
    if isinstance(value, Path):
        return value.name
    if isinstance(value, str):
        if _WINDOWS_ABSOLUTE_PATH.match(value) or value.startswith("/"):
            return value.replace("\\", "/").rsplit("/", 1)[-1]
        return _SECRET_VALUE.sub("[REDACTED]", value)
    return value


def _entry_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AuditLog:
    """Append-only JSONL audit log with a verifiable hash chain."""

    def __init__(self, workspace: CaseWorkspace) -> None:
        self.workspace = workspace
        self.path = workspace.audit_file

    def entries(self) -> Iterator[CaseAuditEntry]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield CaseAuditEntry.model_validate_json(line)

    def append(
        self,
        *,
        action: str,
        object_type: str,
        object_id: str,
        description: str,
        actor: str = "local-user",
        metadata: Mapping[str, Any] | None = None,
    ) -> CaseAuditEntry:
        previous = None
        for previous_entry in self.entries():
            previous = previous_entry.entry_hash
        base = {
            "timestamp": utc_now().isoformat(),
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "description": description,
            "actor": actor,
            "previous_hash": previous,
            "metadata": _safe_metadata(dict(metadata or {})),
        }
        normalized = CaseAuditEntry(**base, entry_hash="")
        digest_payload = normalized.model_dump(mode="json", exclude={"entry_hash"})
        entry = normalized.model_copy(update={"entry_hash": _entry_digest(digest_payload)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return entry

    def verify(self) -> bool:
        previous_hash: str | None = None
        try:
            for entry in self.entries():
                if entry.previous_hash != previous_hash:
                    return False
                payload = entry.model_dump(mode="json", exclude={"entry_hash"})
                if _entry_digest(payload) != entry.entry_hash:
                    return False
                previous_hash = entry.entry_hash
        except (ValueError, json.JSONDecodeError):
            return False
        return True
