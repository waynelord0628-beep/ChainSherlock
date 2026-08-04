from dataclasses import dataclass

from crypto_investigator.domain.transaction import Chain


@dataclass(frozen=True, slots=True)
class Address:
    """Blockchain address identity without transport-specific validation."""

    chain: Chain
    value: str

