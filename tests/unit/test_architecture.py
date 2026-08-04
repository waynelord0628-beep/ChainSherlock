import sys
from types import ModuleType

import pytest

from crypto_investigator.core import Application
from crypto_investigator.plugins import PluginLoader, PluginRegistry
from crypto_investigator.tools import ToolRegistry


class ExamplePlugin:
    name = "example"
    version = "1.0"

    def register(self, application: Application) -> None:
        application.context.state["example"] = True


class ExampleTool:
    name = "example"
    description = "Test-only protocol implementation."

    async def execute(self, arguments):
        return arguments


def test_application_builds_empty_registries():
    application = Application.from_config()
    assert len(application.plugins) == 0
    assert len(application.tools) == 0
    assert application.context.settings is application.settings


def test_plugin_registry_rejects_duplicates():
    registry = PluginRegistry()
    registry.register(ExamplePlugin())
    assert registry.names() == ("example",)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ExamplePlugin())


def test_plugin_loader_loads_explicit_module():
    module_name = "chain_sherlock_test_plugin"
    module = ModuleType(module_name)
    module.plugin = ExamplePlugin()
    sys.modules[module_name] = module
    try:
        registry = PluginRegistry()
        loaded = PluginLoader(registry).load(module_name)
        assert loaded is registry.get("example")
    finally:
        sys.modules.pop(module_name, None)


def test_tool_registry_accepts_protocol_implementation():
    registry = ToolRegistry()
    tool = ExampleTool()
    registry.register(tool)
    assert registry.get("example") is tool
