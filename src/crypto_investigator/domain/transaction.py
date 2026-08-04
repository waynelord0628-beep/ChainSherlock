from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping


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


@dataclass(frozen=True, slots=True)
class Transaction:
    """Canonical transaction consumed by future analyzers and exporters."""

    chain: Chain
    tx_hash: str
    from_address: str | None = None
    to_address: str | None = None
    asset_symbol: str | None = None
    amount: Decimal | None = None
    timestamp: datetime | None = None
    block_number: int | None = None
    fee: Decimal | None = None
    success: bool | None = None
    transaction_type: TransactionType = TransactionType.UNKNOWN
    direction: Direction = Direction.UNKNOWN
    metadata: Mapping[str, Any] = field(default_factory=dict)

