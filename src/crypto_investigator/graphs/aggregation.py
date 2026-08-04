from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from crypto_investigator.domain.transaction import Direction


@dataclass(slots=True)
class EdgeAccumulator:
    source: str
    target: str
    direction: Direction
    asset: str
    transaction_count: int = 0
    amount: Decimal = Decimal("0")
    timestamps: list[datetime] = field(default_factory=list)
    hashes: set[str] = field(default_factory=set)
