import asyncio

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.base import BaseProvider
from crypto_investigator.providers.models import ProviderDescriptor


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[Chain, str], BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        key = (provider.chain, provider.name)
        if key in self._providers:
            raise ValueError(f"Provider already registered: {provider.name}")
        self._providers[key] = provider

    def get(self, chain: Chain, name: str) -> BaseProvider:
        try:
            return self._providers[(chain, name)]
        except KeyError as error:
            raise KeyError(f"Unknown provider for {chain.value}: {name}") from error

    def for_chain(self, chain: Chain) -> tuple[BaseProvider, ...]:
        return tuple(
            provider
            for (provider_chain, _), provider in self._providers.items()
            if provider_chain is chain
        )

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(
            ProviderDescriptor(
                provider.name,
                provider.chain,
                tuple(sorted(provider.capabilities, key=lambda item: item.value)),
                provider.requires_api_key,
            )
            for provider in self._providers.values()
        )

    async def health(self) -> tuple[ProviderDescriptor, ...]:
        providers = tuple(self._providers.values())
        checks = await asyncio.gather(
            *(provider.health_check() for provider in providers)
        )
        return tuple(
            ProviderDescriptor(
                provider.name,
                provider.chain,
                tuple(sorted(provider.capabilities, key=lambda item: item.value)),
                provider.requires_api_key,
                check,
            )
            for provider, check in zip(providers, checks, strict=True)
        )
