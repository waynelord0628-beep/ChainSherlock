from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from crypto_investigator.cases.errors import UnsupportedCaseSchemaError
from crypto_investigator.cases.models import CURRENT_CASE_SCHEMA_VERSION

Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _migrate_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(data)
    if "case_id" not in migrated and "id" in migrated:
        migrated["case_id"] = migrated["id"]
    if "title" not in migrated and "name" in migrated:
        migrated["title"] = migrated["name"]
    migrated.setdefault("description", "")
    migrated.setdefault("status", "open")
    migrated.setdefault("evidence", [])
    migrated.setdefault("metadata", {})
    migrated["schema_version"] = 1
    return migrated


def _migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(data)
    migrated.setdefault("goals", [])
    migrated.setdefault("plans", [])
    migrated["schema_version"] = 2
    return migrated


def _migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(data)
    migrated.setdefault("executions", [])
    migrated.setdefault("latest_execution_id", None)
    migrated.setdefault("active_execution_id", None)
    migrated.setdefault("last_execution_status", None)
    migrated.setdefault("execution_summary", {})
    migrated["schema_version"] = 3
    return migrated


MIGRATIONS: dict[int, Migration] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
}


def migrate_case_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate a copy while preserving unknown fields."""

    migrated = deepcopy(dict(payload))
    version = migrated.get("schema_version", 0)
    if not isinstance(version, int) or version < 0:
        raise UnsupportedCaseSchemaError(f"Invalid case schema version: {version!r}")
    if version > CURRENT_CASE_SCHEMA_VERSION:
        raise UnsupportedCaseSchemaError(
            f"Case schema {version} is newer than supported schema "
            f"{CURRENT_CASE_SCHEMA_VERSION}"
        )
    while version < CURRENT_CASE_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise UnsupportedCaseSchemaError(f"No migration is available from schema {version}")
        migrated = migration(migrated)
        next_version = migrated.get("schema_version")
        if not isinstance(next_version, int) or next_version <= version:
            raise UnsupportedCaseSchemaError(f"Migration from schema {version} made no progress")
        version = next_version
    return migrated
