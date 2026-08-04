from crypto_investigator.plugins.protocol import Plugin


class PluginRegistry:
    """In-memory registry for explicitly loaded plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> Plugin:
        try:
            return self._plugins[name]
        except KeyError as error:
            raise KeyError(f"Plugin not registered: {name}") from error

    def unregister(self, name: str) -> Plugin:
        return self._plugins.pop(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._plugins)

    def __len__(self) -> int:
        return len(self._plugins)

