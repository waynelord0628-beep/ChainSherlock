from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from crypto_investigator.models.transaction import Chain


class AddressSummary(BaseModel):
    chain: Chain
    address: str
    transaction_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    native_received: Decimal = Decimal("0")
    native_sent: Decimal = Decimal("0")
    labels: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

