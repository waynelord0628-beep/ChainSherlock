from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from crypto_investigator.core.application import Application


@runtime_checkable
class Plugin(Protocol):
    """Contract implemented by optional ChainSherlock extensions."""

    name: str
    version: str

    def register(self, application: "Application") -> None:
        """Register the plugin with an application instance."""

