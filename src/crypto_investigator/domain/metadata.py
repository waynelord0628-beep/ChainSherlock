from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Any


class Metadata(Mapping[str, Any]):
    """Immutable metadata attached to a domain entity."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        self._values = MappingProxyType(dict(values or {}))

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"Metadata({dict(self._values)!r})"
