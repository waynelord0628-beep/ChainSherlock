from dataclasses import dataclass

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.models import ProviderCapability


@dataclass(frozen=True, slots=True)
class ChainCapabilityPolicy:
    chain: Chain
    required_capabilities: tuple[ProviderCapability, ...]
    optional_capabilities: tuple[ProviderCapability, ...] = ()
    unsupported_capabilities: tuple[ProviderCapability, ...] = ()


POLICIES = {
    Chain.ETHEREUM: ChainCapabilityPolicy(
        Chain.ETHEREUM,
        (
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TOKEN_TRANSFERS,
        ),
        (
            ProviderCapability.INTERNAL_TRANSACTIONS,
            ProviderCapability.NFT_TRANSFERS,
        ),
    ),
    Chain.TRON: ChainCapabilityPolicy(
        Chain.TRON,
        (
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.TOKEN_TRANSFERS,
        ),
        (ProviderCapability.BALANCE,),
    ),
    Chain.BITCOIN: ChainCapabilityPolicy(
        Chain.BITCOIN,
        (
            ProviderCapability.ADDRESS_TRANSACTIONS,
            ProviderCapability.UTXO,
        ),
        (ProviderCapability.BALANCE,),
        (
            ProviderCapability.TOKEN_TRANSFERS,
            ProviderCapability.INTERNAL_TRANSACTIONS,
        ),
    ),
}


def capability_policy(chain: Chain) -> ChainCapabilityPolicy:
    return POLICIES[chain]


def required_capabilities_complete(chain: Chain, results) -> bool:
    required = set(capability_policy(chain).required_capabilities)
    complete = completed_capabilities(results)
    return required.issubset(complete)


def completed_capabilities(results) -> set[ProviderCapability]:
    return {
        result.capability
        for result in results
        if result.pagination is not None
        and result.pagination.pagination_complete
        and not result.truncated
        and result.completeness.value in {"complete", "empty"}
    }


def unresolved_required_errors(chain: Chain, results, errors):
    required = set(capability_policy(chain).required_capabilities)
    complete = completed_capabilities(results)
    return tuple(
        error
        for error in errors
        if error.capability in required and error.capability not in complete
    )
