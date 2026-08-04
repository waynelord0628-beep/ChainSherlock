from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from dateutil.parser import parse as parse_datetime

from crypto_investigator.domain.metadata import Metadata
from crypto_investigator.domain.transaction import (
    Chain,
    Direction,
    Transaction,
    TransactionType,
)


class Normalizer(Protocol):
    chain: Chain

    def normalize(self, record: Mapping[str, Any]) -> Transaction:
        """Convert a validated canonical raw record into a domain transaction."""


class BaseNormalizer(ABC):
    chain: Chain

    def normalize(self, record: Mapping[str, Any]) -> Transaction:
        return Transaction(
            chain=self.chain,
            tx_hash=str(record["tx_hash"]).strip(),
            timestamp=self._timestamp(record.get("timestamp")),
            block_number=self._optional_int(record.get("block_number")),
            from_address=self.normalize_address(record.get("from_address")),
            to_address=self.normalize_address(record.get("to_address")),
            asset_symbol=self._optional_text(record.get("asset_symbol")),
            asset_contract=self.normalize_address(record.get("asset_contract")),
            amount=Decimal(str(record["amount"]).strip()),
            decimals=self._optional_int(record.get("decimals")),
            direction=self._enum_or_default(
                Direction, record.get("direction"), Direction.UNKNOWN
            ),
            transaction_type=self._enum_or_default(
                TransactionType,
                record.get("transaction_type"),
                TransactionType.UNKNOWN,
            ),
            success=record.get("success"),
            metadata=Metadata({"source_record": dict(record)}),
        )

    @abstractmethod
    def normalize_address(self, value: Any) -> str | None:
        """Apply chain-specific address representation rules."""

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None or not str(value).strip():
            return None
        return str(value).strip()

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or not str(value).strip():
            return None
        return int(value)

    @staticmethod
    def _timestamp(value: Any) -> datetime | None:
        if value is None or not str(value).strip():
            return None
        timestamp = value if isinstance(value, datetime) else parse_datetime(str(value))
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    @staticmethod
    def _enum_or_default(enum_type, value: Any, default):
        if value is None or not str(value).strip():
            return default
        try:
            return enum_type(str(value).strip().casefold())
        except ValueError:
            return default
