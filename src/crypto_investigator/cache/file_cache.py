from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any

from crypto_investigator.cache.keys import CacheKey


class FileCache:
    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    def get(self, key: CacheKey) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if expires_at <= datetime.now(UTC):
                path.unlink(missing_ok=True)
                return None
            return payload["value"]
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None

    def set(
        self, key: CacheKey, value: Any, ttl_seconds: int | None = None
    ) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC)
        payload = {
            "created_at": now.isoformat(),
            "expires_at": (
                now + timedelta(seconds=ttl_seconds or self.ttl_seconds)
            ).isoformat(),
            "value": value,
        }
        path = self._path(key)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def get_or_none(self, key: CacheKey, refresh: bool = False) -> Any | None:
        return None if refresh else self.get(key)

    def clear(self) -> int:
        if not self.directory.exists():
            return 0
        removed = 0
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def _path(self, key: CacheKey) -> Path:
        return self.directory / f"{key.digest}.json"
