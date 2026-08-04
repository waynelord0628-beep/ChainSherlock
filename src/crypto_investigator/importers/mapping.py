from dataclasses import dataclass, field
from typing import Iterable, Mapping


ALIASES: dict[str, tuple[str, ...]] = {
    "from_address": (
        "from",
        "from_address",
        "sender",
        "source",
        "來源地址",
        "轉出地址",
    ),
    "to_address": (
        "to",
        "to_address",
        "receiver",
        "recipient",
        "destination",
        "接收地址",
        "轉入地址",
    ),
    "amount": ("amount", "value", "quantity", "金額"),
    "asset_symbol": ("asset", "asset_symbol", "symbol", "currency", "token"),
    "timestamp": ("timestamp", "time", "datetime", "日期"),
    "tx_hash": ("hash", "tx_hash", "txid", "transaction_hash"),
    "chain": ("chain", "network", "blockchain"),
    "block_number": ("block_number", "block", "block_height"),
    "asset_contract": ("asset_contract", "token_contract", "contract_address"),
    "decimals": ("decimals", "token_decimals"),
    "direction": ("direction",),
    "transaction_type": ("transaction_type", "type"),
}


class ColumnMappingError(ValueError):
    def __init__(self, candidates: Mapping[str, tuple[str, ...]], missing: tuple[str, ...]) -> None:
        self.candidates = dict(candidates)
        self.missing = missing
        details = []
        if candidates:
            details.append(f"ambiguous candidates={dict(candidates)}")
        if missing:
            details.append(f"missing={list(missing)}")
        super().__init__("Unable to map columns reliably: " + "; ".join(details))


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    canonical_to_source: dict[str, str]
    candidates: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def apply(self, row: Mapping[str, object]) -> dict[str, object]:
        return {
            canonical: row.get(source)
            for canonical, source in self.canonical_to_source.items()
        }


class MappingEngine:
    required_fields = ("amount", "timestamp", "tx_hash")

    def resolve(
        self,
        columns: Iterable[object],
        overrides: Mapping[str, str] | None = None,
    ) -> ColumnMapping:
        source_columns = [str(column) for column in columns]
        normalized = {column: self._normalize(column) for column in source_columns}
        overrides = dict(overrides or {})
        resolved: dict[str, str] = {}
        candidates: dict[str, tuple[str, ...]] = {}

        for canonical, source in overrides.items():
            if canonical not in ALIASES:
                raise ValueError(f"Unknown canonical field: {canonical}")
            if source not in source_columns:
                raise ValueError(f"Column not found: {source}")
            resolved[canonical] = source

        for canonical, aliases in ALIASES.items():
            if canonical in resolved:
                continue
            alias_set = {self._normalize(alias) for alias in aliases}
            matches = tuple(
                column for column in source_columns if normalized[column] in alias_set
            )
            if len(matches) == 1:
                resolved[canonical] = matches[0]
            elif len(matches) > 1:
                candidates[canonical] = matches

        missing = tuple(field for field in self.required_fields if field not in resolved)
        if candidates or missing:
            raise ColumnMappingError(candidates, missing)
        return ColumnMapping(resolved)

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold().replace(" ", "_").replace("-", "_")
