from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Mapping

from crypto_investigator.domain.transaction import Chain


class ProviderCapability(StrEnum):
    ADDRESS_TRANSACTIONS = "address_transactions"
    TRANSACTION = "transaction"
    TOKEN_TRANSFERS = "token_transfers"
    INTERNAL_TRANSACTIONS = "internal_transactions"
    BALANCE = "balance"
    UTXO = "utxo"
    NFT_TRANSFERS = "nft_transfers"
    CONTRACT_METADATA = "contract_metadata"


class Completeness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class ProviderRawRecord:
    chain: Chain
    source_provider: str
    source_type: str
    tx_hash: str
    block_number: int | None = None
    timestamp: datetime | None = None
    from_address: str | None = None
    to_address: str | None = None
    asset_symbol: str | None = None
    asset_contract: str | None = None
    amount_raw: str | None = None
    decimals: int | None = None
    success: bool | None = None
    transaction_type: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw_reference: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderPage:
    records: tuple[ProviderRawRecord, ...]
    next_cursor: str | None = None
    raw_response: Any = None


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider: str
    chain: Chain
    capability: ProviderCapability
    records: tuple[ProviderRawRecord, ...]
    completeness: Completeness
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    warnings: tuple[str, ...] = ()
    errors: tuple[Exception, ...] = ()
    missing_data: tuple[str, ...] = ()
    pages_fetched: int = 0


@dataclass(frozen=True, slots=True)
class ProviderBalance:
    provider: str
    chain: Chain
    identifier: str
    amount_raw: str
    decimals: int
    asset_symbol: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class HealthCheck:
    provider: str
    chain: Chain
    available: bool
    safe_message: str = "ok"


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    name: str
    chain: Chain
    capabilities: tuple[ProviderCapability, ...]
    requires_api_key: bool
    health: HealthCheck | None = None
