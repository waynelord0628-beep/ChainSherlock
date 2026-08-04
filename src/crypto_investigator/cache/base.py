from typing import Any, Protocol

from crypto_investigator.cache.keys import CacheKey


class Cache(Protocol):
    def get(self, key: CacheKey) -> Any | None:
        """Return cached data or None for a miss/expired entry."""

    def set(self, key: CacheKey, value: Any, ttl_seconds: int | None = None) -> None:
        """Persist JSON-compatible data."""

    def clear(self) -> int:
        """Clear entries and return the number removed."""
