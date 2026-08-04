from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Chain(StrEnum):
    ETHEREUM = "ethereum"
    TRON = "tron"
    BITCOIN = "bitcoin"


class Direction(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SELF = "self"
    UNKNOWN = "unknown"


class TransactionType(StrEnum):
    NATIVE_TRANSFER = "native_transfer"
    TOKEN_TRANSFER = "token_transfer"
    INTERNAL_TRANSFER = "internal_transfer"
    CONTRACT_CALL = "contract_call"
    SWAP = "swap"
    NFT_TRANSFER = "nft_transfer"
    COINBASE = "coinbase"
    UTXO_TRANSFER = "utxo_transfer"
    UNKNOWN = "unknown"


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

