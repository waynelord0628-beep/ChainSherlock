from dataclasses import dataclass

from crypto_investigator.domain.address import Address


@dataclass(frozen=True, slots=True)
class Counterparty:
    """Domain identity for an address related to an investigation target."""

    address: Address
    labels: tuple[str, ...] = ()

