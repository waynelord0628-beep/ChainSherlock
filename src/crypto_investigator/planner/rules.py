from __future__ import annotations

from collections.abc import Iterable

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.planner.models import ProviderRequirement
from crypto_investigator.providers.models import ProviderCapability, ProviderDescriptor

ADDRESS_CAPABILITIES: dict[Chain, tuple[ProviderCapability, ...]] = {
    Chain.TRON: (
        ProviderCapability.ADDRESS_TRANSACTIONS,
        ProviderCapability.TOKEN_TRANSFERS,
    ),
    Chain.ETHEREUM: (
        ProviderCapability.ADDRESS_TRANSACTIONS,
        ProviderCapability.TOKEN_TRANSFERS,
        ProviderCapability.INTERNAL_TRANSACTIONS,
    ),
    Chain.BITCOIN: (
        ProviderCapability.ADDRESS_TRANSACTIONS,
        ProviderCapability.UTXO,
    ),
}

STRUCTURED_SUFFIXES = frozenset({".csv", ".xls", ".xlsx", ".json"})


def capability_requirements(
    chain: Chain,
    descriptors: Iterable[ProviderDescriptor],
) -> tuple[ProviderRequirement, ...]:
    available = tuple(item for item in descriptors if item.chain is chain)
    requirements: list[ProviderRequirement] = []
    for capability in ADDRESS_CAPABILITIES[chain]:
        provider = next(
            (item for item in available if capability in item.capabilities),
            None,
        )
        requirements.append(
            ProviderRequirement(
                chain=chain,
                capability=capability.value,
                provider=provider.name if provider else None,
                available=provider is not None,
            )
        )
    return tuple(requirements)
