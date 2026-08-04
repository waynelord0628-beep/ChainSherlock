from dataclasses import dataclass, field
from typing import Any, Mapping

from crypto_investigator.domain.address import Address
from crypto_investigator.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class InvestigationCase:
    """Aggregate boundary for a future investigation workflow."""

    case_id: str
    title: str
    addresses: tuple[Address, ...] = ()
    transactions: tuple[Transaction, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

