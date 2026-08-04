from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from crypto_investigator.domain.transaction import Chain, Direction, TransactionType


class Transaction(BaseModel):
    chain: Chain
    tx_hash: str
    from_address: str | None = None
    to_address: str | None = None
    amount_normalized: Decimal | None = None
    asset_symbol: str | None = None
    block_number: int | None = None
    block_timestamp: datetime | None = None
    asset_contract: str | None = None
    amount_raw: str | None = None
    decimals: int | None = None
    fee: Decimal | None = None
    success: bool | None = None
    transaction_type: TransactionType = TransactionType.UNKNOWN
    direction: Direction = Direction.UNKNOWN
    source_provider: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
