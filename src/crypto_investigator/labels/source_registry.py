"""Evidence-preserving, multi-source address label registry."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping

from crypto_investigator.labels.registry import normalize_label_address


CHAIN_ALIASES = {
    "bnb chain": "bnb",
    "bsc": "bnb",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "tron": "tron",
    "trx": "tron",
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
}

CATEGORY_ALIASES = {
    "cex": "exchange",
    "centralized_exchange": "exchange",
    "sanctions": "sanctioned",
}

SOURCE_PRIORITY = {
    "manual_confirmed": 100,
    "official": 90,
    "trusted_local": 80,
    "dune_curated": 70,
    "provider_label": 60,
    "public_curated": 50,
    "public_reported": 30,
    "unverified_candidate": 10,
}


@dataclass(frozen=True, slots=True)
class LabelSnapshot:
    snapshot_id: str
    source: str
    imported_at: datetime
    source_updated_at: datetime | None = None
    record_count: int = 0
    sha256: str | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SourceLabelRecord:
    chain: str
    address: str
    label: str
    category: str
    source: str
    verification_status: str
    snapshot_id: str
    source_record_id: str | None = None
    source_evidence: str | None = None
    source_website: str | None = None
    subcategory: str | None = None
    confidence: str = "medium"
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None
    imported_at: datetime | None = None

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return self.chain, self.address, self.label.casefold(), self.source


@dataclass(frozen=True, slots=True)
class LabelResolution:
    chain: str
    address: str
    preferred: SourceLabelRecord | None
    matches: tuple[SourceLabelRecord, ...]
    conflicting_labels: tuple[str, ...]


class MultiSourceLabelRegistry:
    def __init__(
        self,
        records: Iterable[SourceLabelRecord] = (),
        snapshots: Iterable[LabelSnapshot] = (),
    ):
        unique = {item.identity: item for item in records}
        self.records = tuple(
            unique[key]
            for key in sorted(unique, key=lambda value: tuple(str(item) for item in value))
        )
        self.snapshots = tuple(sorted(snapshots, key=lambda item: item.snapshot_id))

    @classmethod
    def import_dune_cex_csv(
        cls, path: Path, *, snapshot_id: str | None = None
    ) -> "MultiSourceLabelRegistry":
        rows = _csv_rows(path)
        snapshot = _snapshot(path, "dune_cex_addresses", snapshot_id, len(rows))
        records = []
        for row in rows:
            chain, address = _chain_address(row)
            label = _first(row, "cex_name", "label", "name")
            if not chain or not address or not label:
                continue
            distinct = _optional(row, "distinct_name")
            records.append(
                SourceLabelRecord(
                    chain=chain,
                    address=address,
                    label=label,
                    category="exchange",
                    subcategory=distinct or None,
                    source="dune_cex_addresses",
                    verification_status="dune_curated",
                    snapshot_id=snapshot.snapshot_id,
                    source_record_id=_optional(row, "source_record_id") or None,
                    source_evidence=_optional(row, "source_evidence") or None,
                    confidence="high",
                    updated_at=_datetime(_optional(row, "added_date")),
                    imported_at=snapshot.imported_at,
                )
            )
        return cls(records, (snapshot,))

    @classmethod
    def import_dune_owner_csv(
        cls, path: Path, *, snapshot_id: str | None = None
    ) -> "MultiSourceLabelRegistry":
        rows = _csv_rows(path)
        snapshot = _snapshot(path, "dune_owner_addresses", snapshot_id, len(rows))
        records = []
        for row in rows:
            chain, address = _chain_address(row)
            label = _first(
                row, "label", "custody_owner", "account_owner", "contract_name", "name"
            )
            if not chain or not address or not label:
                continue
            raw_category = _first(row, "category", "primary_category") or "unknown"
            category = CATEGORY_ALIASES.get(raw_category.casefold(), raw_category.casefold())
            records.append(
                SourceLabelRecord(
                    chain=chain,
                    address=address,
                    label=label,
                    category=category,
                    subcategory=_optional(row, "contract_name") or None,
                    source="dune_owner_addresses",
                    verification_status="dune_curated",
                    snapshot_id=snapshot.snapshot_id,
                    source_record_id=_optional(row, "owner_key") or None,
                    source_evidence=_first(
                        row, "source_evidence", "identifying_transaction"
                    )
                    or None,
                    source_website=_optional(row, "source_website") or None,
                    confidence="high" if _optional(row, "source_evidence") else "medium",
                    first_seen_at=_datetime(_optional(row, "created_at")),
                    updated_at=_datetime(_optional(row, "updated_at")),
                    imported_at=snapshot.imported_at,
                )
            )
        return cls(records, (snapshot,))

    @classmethod
    def import_ofac_digital_currency_csv(
        cls, path: Path, *, snapshot_id: str | None = None
    ) -> "MultiSourceLabelRegistry":
        """Import normalized OFAC rows with digital currency address columns.

        The importer accepts either ``id_type``/``id_value`` rows or wide CSV
        columns named ``Digital Currency Address - <asset>``.
        """

        rows = _csv_rows(path)
        snapshot = _snapshot(path, "ofac_sdn", snapshot_id, len(rows))
        records = []
        for row_index, row in enumerate(rows, start=1):
            name = _first(row, "name", "sdn_name", "entity_name") or "OFAC SDN entry"
            program = _optional(row, "program")
            candidates: list[tuple[str, str]] = []
            id_type = _optional(row, "id_type")
            id_value = _optional(row, "id_value")
            if id_type.casefold().startswith("digital currency address") and id_value:
                candidates.append((id_type, id_value))
            for key, value in row.items():
                if key.casefold().startswith("digital currency address") and str(value).strip():
                    candidates.append((key, str(value).strip()))
            for address_type, address in candidates:
                chain = _ofac_chain(address_type, address)
                normalized = normalize_label_address(chain, address)
                records.append(
                    SourceLabelRecord(
                        chain=chain,
                        address=normalized,
                        label=name,
                        category="sanctioned",
                        subcategory=program or None,
                        source="ofac_sdn",
                        verification_status="official",
                        snapshot_id=snapshot.snapshot_id,
                        source_record_id=_first(row, "uid", "sdn_uid") or str(row_index),
                        source_evidence=_optional(row, "source_evidence") or None,
                        source_website="https://sanctionssearch.ofac.treas.gov/",
                        confidence="high",
                        updated_at=_datetime(_optional(row, "updated_at")),
                        imported_at=snapshot.imported_at,
                    )
                )
        return cls(records, (snapshot,))

    @classmethod
    def combine(cls, *registries: "MultiSourceLabelRegistry"):
        return cls(
            (record for registry in registries for record in registry.records),
            (snapshot for registry in registries for snapshot in registry.snapshots),
        )

    def resolve(self, chain: str, address: str) -> LabelResolution:
        normalized_chain = _normalize_chain(chain)
        normalized_address = normalize_label_address(normalized_chain, address)
        matches = tuple(
            item
            for item in self.records
            if item.chain == normalized_chain and item.address == normalized_address
        )
        preferred = max(
            matches,
            key=lambda item: (
                SOURCE_PRIORITY.get(item.verification_status, 0),
                item.updated_at or datetime.min.replace(tzinfo=UTC),
                item.label.casefold(),
            ),
            default=None,
        )
        labels = tuple(sorted({item.label for item in matches}))
        return LabelResolution(
            normalized_chain,
            normalized_address,
            preferred,
            matches,
            labels if len(labels) > 1 else (),
        )

    def write_sqlite(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.executescript(_SCHEMA)
            connection.execute("BEGIN")
            try:
                for snapshot in self.snapshots:
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO label_snapshots
                        (snapshot_id, source, imported_at, source_updated_at,
                         record_count, sha256, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot.snapshot_id,
                            snapshot.source,
                            snapshot.imported_at.isoformat(),
                            _iso(snapshot.source_updated_at),
                            snapshot.record_count,
                            snapshot.sha256,
                            snapshot.notes,
                        ),
                    )
                for item in self.records:
                    payload = asdict(item)
                    for key in ("first_seen_at", "updated_at", "imported_at"):
                        payload[key] = _iso(payload[key])
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO label_records
                        (chain, address, label, category, subcategory, source,
                         source_record_id, source_evidence, source_website,
                         verification_status, confidence, snapshot_id,
                         first_seen_at, updated_at, imported_at)
                        VALUES (:chain, :address, :label, :category, :subcategory,
                         :source, :source_record_id, :source_evidence, :source_website,
                         :verification_status, :confidence, :snapshot_id,
                         :first_seen_at, :updated_at, :imported_at)
                        """,
                        payload,
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return path


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [
            {str(key).strip(): str(value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(stream)
        ]


def _snapshot(
    path: Path, source: str, snapshot_id: str | None, record_count: int
) -> LabelSnapshot:
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    imported_at = datetime.now(UTC)
    return LabelSnapshot(
        snapshot_id=snapshot_id or f"{source}-{digest[:16]}",
        source=source,
        imported_at=imported_at,
        record_count=record_count,
        sha256=digest,
    )


def _chain_address(row: Mapping[str, str]) -> tuple[str, str]:
    chain = _normalize_chain(_first(row, "blockchain", "chain"))
    address = normalize_label_address(chain, _first(row, "address"))
    return chain, address


def _normalize_chain(value: str) -> str:
    normalized = str(value).strip().casefold()
    return CHAIN_ALIASES.get(normalized, normalized)


def _first(row: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = _optional(row, key)
        if value:
            return value
    return ""


def _optional(row: Mapping[str, str], key: str) -> str:
    return str(row.get(key, "") or "").strip()


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _ofac_chain(address_type: str, address: str) -> str:
    kind = address_type.casefold()
    if "trx" in kind or address.startswith("T"):
        return "tron"
    if "xbt" in kind or "btc" in kind:
        return "bitcoin"
    if "eth" in kind or address.casefold().startswith("0x"):
        return "ethereum"
    return "unknown"


_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS label_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    source_updated_at TEXT,
    record_count INTEGER NOT NULL,
    sha256 TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS label_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain TEXT NOT NULL,
    address TEXT NOT NULL,
    label TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    source TEXT NOT NULL,
    source_record_id TEXT,
    source_evidence TEXT,
    source_website TEXT,
    verification_status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    first_seen_at TEXT,
    updated_at TEXT,
    imported_at TEXT,
    UNIQUE(chain, address, label, source),
    FOREIGN KEY(snapshot_id) REFERENCES label_snapshots(snapshot_id)
);
CREATE INDEX IF NOT EXISTS idx_label_chain_address
ON label_records(chain, address);
CREATE INDEX IF NOT EXISTS idx_label_category
ON label_records(category);
CREATE INDEX IF NOT EXISTS idx_label_source
ON label_records(source);
"""

