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


class ProviderOrdering(StrEnum):
    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"
    PROVIDER_DEFINED = "provider_defined"


class PaginationStrategy(StrEnum):
    PAGE_NUMBER = "page_number"
    OFFSET = "offset"
    CURSOR = "cursor"
    FINGERPRINT = "fingerprint"
    BEFORE_TXID = "before_txid"
    BLOCK_RANGE = "block_range"
    PROVIDER_DEFINED = "provider_defined"


@dataclass(frozen=True, slots=True)
class PaginationMetadata:
    provider: str
    chain: Chain
    capability: ProviderCapability
    ordering: ProviderOrdering = ProviderOrdering.PROVIDER_DEFINED
    pagination_strategy: PaginationStrategy = (
        PaginationStrategy.PROVIDER_DEFINED
    )
    next_cursor: str | None = None
    has_more: bool = False
    pagination_complete: bool = False
    fetched_records: int = 0
    accepted_records: int = 0
    excluded_by_scope: int = 0
    rejected_records: int = 0
    deduplicated_records: int = 0
    earliest_fetched_at: datetime | None = None
    latest_fetched_at: datetime | None = None
    truncated: bool = False
    truncation_reason: str | None = None
    completeness: Completeness = Completeness.PARTIAL


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
    truncated: bool = False
    truncation_reason: str | None = None
    fetched_records: int = 0
    available_more: bool = False
    pagination: PaginationMetadata | None = None


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
