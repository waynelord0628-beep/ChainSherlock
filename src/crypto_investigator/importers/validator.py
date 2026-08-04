from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import math
from typing import Any, Iterable, Mapping

from dateutil.parser import ParserError, parse as parse_datetime

from crypto_investigator.utils.address_validation import is_valid_address


FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    row: int
    field: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid_records: tuple[dict[str, Any], ...]
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


class DataValidator:
    required_fields = ("tx_hash", "timestamp", "amount")

    def validate(self, records: Iterable[Mapping[str, Any]]) -> ValidationResult:
        valid: list[dict[str, Any]] = []
        issues: list[ValidationIssue] = []
        seen_hashes: set[str] = set()

        for row_number, source in enumerate(records, start=2):
            record = dict(source)
            row_issues = self._validate_record(row_number, record)
            tx_hash = str(record.get("tx_hash") or "").strip()
            if tx_hash and tx_hash in seen_hashes:
                row_issues.append(
                    ValidationIssue(row_number, "tx_hash", "duplicate_transaction", "Duplicate transaction hash")
                )
            elif tx_hash:
                seen_hashes.add(tx_hash)
            if row_issues:
                issues.extend(row_issues)
            else:
                valid.append(record)

        return ValidationResult(tuple(valid), tuple(issues))

    def _validate_record(self, row: int, record: Mapping[str, Any]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for field in self.required_fields:
            if self._is_empty(record.get(field)):
                issues.append(ValidationIssue(row, field, "empty_value", "Required value is empty"))

        for field, value in record.items():
            if isinstance(value, str) and value.lstrip().startswith(FORMULA_PREFIXES):
                issues.append(
                    ValidationIssue(row, field, "formula_injection", "Spreadsheet formula input is not allowed")
                )

        amount = record.get("amount")
        if not self._is_empty(amount) and not self._valid_amount(amount):
            issues.append(ValidationIssue(row, "amount", "invalid_amount", "Amount must be a finite number"))

        timestamp = record.get("timestamp")
        if not self._is_empty(timestamp) and not self._valid_timestamp(timestamp):
            issues.append(ValidationIssue(row, "timestamp", "invalid_timestamp", "Timestamp is invalid"))

        address_values = [record.get("from_address"), record.get("to_address")]
        if all(self._is_empty(value) for value in address_values):
            issues.append(ValidationIssue(row, "address", "empty_value", "At least one address is required"))
        for field in ("from_address", "to_address"):
            value = record.get(field)
            if not self._is_empty(value) and not is_valid_address(str(value).strip()):
                issues.append(ValidationIssue(row, field, "invalid_address", "Address format is invalid"))
        return issues

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _valid_amount(value: Any) -> bool:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return False
        return amount.is_finite() and not math.isnan(float(amount))

    @staticmethod
    def _valid_timestamp(value: Any) -> bool:
        if isinstance(value, datetime):
            return True
        try:
            parse_datetime(str(value))
        except (ParserError, ValueError, OverflowError, TypeError):
            return False
        return True

