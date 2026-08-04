from pathlib import Path

from crypto_investigator.config import load_config
from crypto_investigator.core.context import Context
from crypto_investigator.core.settings import Settings
from crypto_investigator.plugins.loader import PluginLoader
from crypto_investigator.plugins.registry import PluginRegistry
from crypto_investigator.tools.registry import ToolRegistry


class Application:
    """Composition root for ChainSherlock runtime services."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.plugins = PluginRegistry()
        self.tools = ToolRegistry()
        self.context = Context(settings, self.plugins, self.tools)
        self.plugin_loader = PluginLoader(self.plugins)

    @classmethod
    def from_config(cls, path: Path | str = Path("config/default.yaml")) -> "Application":
        return cls(load_config(path))

