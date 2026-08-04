from dataclasses import dataclass

from crypto_investigator.domain.transaction import Chain


@dataclass(frozen=True, slots=True)
class Asset:
    """Native or token asset referenced by a domain transaction."""

    chain: Chain
    symbol: str
    contract_address: str | None = None
    decimals: int | None = None

