from dataclasses import dataclass, field
from typing import Any

from crypto_investigator.core.settings import Settings
from crypto_investigator.plugins.registry import PluginRegistry
from crypto_investigator.tools.registry import ToolRegistry


@dataclass(slots=True)
class Context:
    """Shared runtime state passed through the application."""

    settings: Settings
    plugins: PluginRegistry
    tools: ToolRegistry
    state: dict[str, Any] = field(default_factory=dict)

