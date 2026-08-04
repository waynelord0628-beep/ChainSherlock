from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    """Contract for future application tools."""

    name: str
    description: str

    async def execute(self, arguments: Mapping[str, Any]) -> Any:
        """Execute a tool with validated arguments."""

