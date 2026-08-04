from importlib import import_module
from types import ModuleType
from typing import Any

from crypto_investigator.plugins.protocol import Plugin
from crypto_investigator.plugins.registry import PluginRegistry


class PluginLoader:
    """Load explicitly named plugin modules into a registry."""

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    def load(self, module_path: str) -> Plugin:
        module = import_module(module_path)
        plugin = self._resolve_plugin(module)
        self.registry.register(plugin)
        return plugin

    @staticmethod
    def _resolve_plugin(module: ModuleType) -> Plugin:
        plugin: Any = getattr(module, "plugin", None)
        if plugin is None:
            factory = getattr(module, "create_plugin", None)
            if not callable(factory):
                raise TypeError("Plugin module must expose 'plugin' or 'create_plugin()'")
            plugin = factory()
        if not isinstance(plugin, Plugin):
            raise TypeError("Loaded object does not satisfy the Plugin protocol")
        return plugin

