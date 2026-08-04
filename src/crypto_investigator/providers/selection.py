from crypto_investigator.config import Settings
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.errors import UnsupportedCapabilityError
from crypto_investigator.providers.models import ProviderCapability
from crypto_investigator.providers.registry import ProviderRegistry


class ProviderSelectionPolicy:
    def __init__(self, registry: ProviderRegistry, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings

    def candidates(
        self,
        chain: Chain,
        capability: ProviderCapability,
        requested: str | None = None,
    ) -> tuple[BaseProvider, ...]:
        config = getattr(self.settings.providers, chain.value)
        names = (requested,) if requested else (config.primary, *config.fallback)
        providers = tuple(self.registry.get(chain, name) for name in names)
        supported = tuple(
            provider for provider in providers if provider.supports(capability)
        )
        if not supported:
            raise UnsupportedCapabilityError(
                provider=requested or config.primary,
                chain=chain,
                capability=capability,
                safe_message=f"Capability not supported: {capability.value}",
                missing_data_category=capability.value,
            )
        return supported
