from abc import ABC, abstractmethod

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.errors import UnsupportedCapabilityError
from crypto_investigator.providers.models import (
    HealthCheck,
    ProviderBalance,
    ProviderCapability,
    ProviderResult,
)


class BaseProvider(ABC):
    chain: Chain
    name: str
    capabilities: frozenset[ProviderCapability] = frozenset()
    requires_api_key: bool = False

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    @abstractmethod
    async def health_check(self) -> HealthCheck:
        """Return availability without exposing secrets."""

    async def get_address_transactions(self, address: str, **kwargs) -> ProviderResult:
        self._unsupported(ProviderCapability.ADDRESS_TRANSACTIONS)

    async def get_transaction(self, tx_hash: str, **kwargs) -> ProviderResult:
        self._unsupported(ProviderCapability.TRANSACTION)

    async def get_token_transfers(self, address: str, **kwargs) -> ProviderResult:
        self._unsupported(ProviderCapability.TOKEN_TRANSFERS)

    async def get_internal_transactions(self, address: str, **kwargs) -> ProviderResult:
        self._unsupported(ProviderCapability.INTERNAL_TRANSACTIONS)

    async def get_utxos(self, address: str, **kwargs) -> ProviderResult:
        self._unsupported(ProviderCapability.UTXO)

    async def get_balance(self, address: str, **kwargs) -> ProviderBalance:
        self._unsupported(ProviderCapability.BALANCE)

    def _unsupported(self, capability: ProviderCapability):
        raise UnsupportedCapabilityError(
            provider=self.name,
            chain=self.chain,
            capability=capability,
            safe_message=f"Capability not supported: {capability.value}",
            missing_data_category=capability.value,
        )
