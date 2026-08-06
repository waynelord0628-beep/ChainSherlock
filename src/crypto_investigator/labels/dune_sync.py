"""Bulk Dune label synchronization into the local SQLite registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx

from crypto_investigator.labels.registry import normalize_label_address
from crypto_investigator.labels.source_registry import (
    CATEGORY_ALIASES,
    CHAIN_ALIASES,
    LabelResolution,
    LabelSnapshot,
    MultiSourceLabelRegistry,
    SOURCE_PRIORITY,
    SourceLabelRecord,
    _SCHEMA,
)


DUNE_API_BASE = "https://api.dune.com/api/v1"

DUNE_CEX_SQL = """
SELECT blockchain, to_hex(address) AS address_hex,
       cex_name, distinct_name, added_by, added_date
FROM cex.addresses
{where_clause}
ORDER BY blockchain, address
""".strip()

DUNE_OWNER_SQL = """
SELECT a.blockchain,
       CASE
         WHEN a.blockchain = 'tron' THEN from_utf8(a.address)
         WHEN a.blockchain IN ('ethereum', 'bnb', 'arbitrum', 'optimism', 'polygon')
           THEN concat('0x', to_hex(a.address))
         ELSE from_utf8(a.address)
       END AS address,
       a.custody_owner, a.account_owner, a.contract_name,
       COALESCE(d.primary_category, 'unknown') AS primary_category,
       a.source, COALESCE(a.source_website, d.website) AS source_website,
       a.owner_key, a.source_evidence, a.identifying_transaction,
       a.created_at, a.updated_at
FROM labels.owner_addresses a
LEFT JOIN labels.owner_details d ON a.owner_key = d.owner_key
WHERE a.blockchain IN ({chains})
ORDER BY a.blockchain, address
""".strip()

DUNE_LABELS_SQL = """
SELECT blockchain, to_hex(address) AS address_hex, name, category,
       contributor, source, created_at, updated_at, model_name, label_type
FROM labels.addresses
{where_clause}
ORDER BY blockchain, address
""".strip()

DUNE_DEPOSIT_LOOKUP_SQL = """
SELECT blockchain, to_hex(address) AS address_hex, cex_name,
       first_deposit_token_standard, deposit_first_block_time,
       consolidation_first_block_time, deposit_count, consolidation_count,
       amount_deposited, consolidation_unique_key, deposit_unique_key
FROM cex.deposit_addresses
WHERE blockchain = '{chain}'
  AND address = from_hex('{address_hex}')
""".strip()

OWNER_SERVICE_CATEGORIES = (
    "Centralized Exchange",
    "Payment Processing",
    "Real World Asset Services",
    "Privacy Services",
)

CORE_CONTRACT_PREDICATE = """
(
  d.primary_category = 'Bridge'
  OR (
    d.primary_category = 'Decentralized Exchange'
    AND (
      lower(coalesce(a.contract_name, '')) LIKE '%swap%'
      OR lower(coalesce(a.contract_name, '')) LIKE '%router%'
      OR lower(coalesce(a.contract_name, '')) LIKE '%aggregator%'
    )
    AND lower(coalesce(a.contract_name, '')) NOT LIKE '%pair%'
    AND lower(coalesce(a.contract_name, '')) NOT LIKE '%pool%'
  )
)
""".strip()


class DuneSyncError(RuntimeError):
    """Raised when Dune cannot provide a complete, valid snapshot."""


@dataclass(frozen=True, slots=True)
class DuneSyncResult:
    dataset: str
    execution_id: str
    fetched_rows: int
    imported_records: int
    snapshot_id: str
    database: Path


EVM_CHAINS = {
    "abstract",
    "arbitrum",
    "avalanche_c",
    "base",
    "berachain",
    "bnb",
    "celo",
    "ethereum",
    "fantom",
    "gnosis",
    "ink",
    "kaia",
    "katana",
    "linea",
    "mantle",
    "nova",
    "opbnb",
    "optimism",
    "polygon",
    "scroll",
    "sei",
    "unichain",
    "worldchain",
    "zkevm",
    "zksync",
    "zora",
}


class DuneLabelClient:
    """Minimal Dune client with bounded polling and result pagination."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DUNE_API_BASE,
        timeout: float = 30.0,
        page_size: int = 10_000,
        poll_interval: float = 1.0,
        max_polls: int = 600,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key.strip():
            raise ValueError("Dune API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self.transport = transport

    def execute(self, sql: str) -> tuple[str, list[dict[str, Any]]]:
        headers = {"X-DUNE-API-KEY": self.api_key}
        with httpx.Client(
            headers=headers,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            response = client.post(
                f"{self.base_url}/sql/execute",
                json={"sql": sql, "performance": "medium"},
            )
            self._raise(response)
            execution_id = str(response.json().get("execution_id") or "")
            if not execution_id:
                raise DuneSyncError("Dune response did not include execution_id")
            self._wait(client, execution_id)
            return execution_id, self._results(client, execution_id)

    def _wait(self, client: httpx.Client, execution_id: str) -> None:
        for _ in range(self.max_polls):
            response = client.get(f"{self.base_url}/execution/{execution_id}/status")
            self._raise(response)
            payload = response.json()
            state = str(payload.get("state") or "")
            if state == "QUERY_STATE_COMPLETED":
                return
            if state in {
                "QUERY_STATE_FAILED",
                "QUERY_STATE_CANCELLED",
                "QUERY_STATE_EXPIRED",
            }:
                error = payload.get("error") or {}
                error_type = str(error.get("type") or "unknown")
                message = " ".join(str(error.get("message") or "").split())[:500]
                detail = f": {error_type}"
                if message:
                    detail += f" - {message}"
                raise DuneSyncError(f"Dune execution ended with state {state}{detail}")
            if self.poll_interval:
                time.sleep(self.poll_interval)
        raise DuneSyncError("Dune execution polling limit exceeded")

    def _results(
        self, client: httpx.Client, execution_id: str
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = client.get(
                f"{self.base_url}/execution/{execution_id}/results",
                params={"limit": self.page_size, "offset": offset},
            )
            self._raise(response)
            payload = response.json()
            result = payload.get("result") or {}
            page = result.get("rows") or []
            if not isinstance(page, list):
                raise DuneSyncError("Dune result rows were not a list")
            rows.extend(dict(item) for item in page)
            next_offset = payload.get("next_offset")
            if next_offset is None:
                next_offset = result.get("next_offset")
            if next_offset is None or not page:
                break
            next_value = int(next_offset)
            if next_value <= offset:
                raise DuneSyncError("Dune pagination did not advance")
            offset = next_value
        return rows

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.is_success:
            return
        request_id = response.headers.get("x-request-id", "")
        suffix = f" (request_id={request_id})" if request_id else ""
        raise DuneSyncError(f"Dune HTTP {response.status_code}{suffix}")


class LocalLabelDatabase:
    """Persistent offline lookup and incremental snapshot storage."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.executescript(_SCHEMA)

    def import_registry(self, registry: MultiSourceLabelRegistry) -> None:
        registry.write_sqlite(self.path)

    def resolve(self, chain: str, address: str) -> LabelResolution:
        normalized_chain = CHAIN_ALIASES.get(chain.strip().casefold(), chain.strip().casefold())
        normalized_address = normalize_label_address(normalized_chain, address)
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT chain, address, label, category, source,
                       verification_status, snapshot_id, source_record_id,
                       source_evidence, source_website, subcategory, confidence,
                       first_seen_at, updated_at, imported_at
                FROM label_records
                WHERE chain = ? AND address = ?
                """,
                (normalized_chain, normalized_address),
            ).fetchall()
        matches = tuple(_row_record(row) for row in rows)
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


def sync_dune_dataset(
    *,
    client: DuneLabelClient,
    database: Path,
    dataset: str,
    chains: Iterable[str],
    categories: Iterable[str] = (),
) -> DuneSyncResult:
    raw_chains = {item.strip().casefold() for item in chains if item.strip()}
    all_chains = "all" in raw_chains
    normalized_chains = tuple(
        sorted(
            {
                CHAIN_ALIASES.get(item, item)
                for item in raw_chains
                if item != "all"
            }
        )
    )
    if not all_chains and not normalized_chains:
        raise ValueError("At least one chain is required")
    quoted = ", ".join("'" + item.replace("'", "''") + "'" for item in normalized_chains)
    if dataset == "cex":
        where_clause = (
            "" if all_chains else f"WHERE blockchain IN ({quoted})"
        )
        sql = DUNE_CEX_SQL.format(where_clause=where_clause)
        source = "dune_cex_addresses"
    elif dataset == "owners":
        where_clause = "" if all_chains else f"WHERE a.blockchain IN ({quoted})"
        sql = DUNE_OWNER_SQL.replace(
            "WHERE a.blockchain IN ({chains})", where_clause
        )
        source = "dune_owner_addresses"
    elif dataset in {"contracts", "services"}:
        predicates = []
        if not all_chains:
            predicates.append(f"a.blockchain IN ({quoted})")
        if dataset == "contracts":
            predicates.append(CORE_CONTRACT_PREDICATE)
        else:
            service_sql = ", ".join(
                "'" + item.replace("'", "''") + "'"
                for item in OWNER_SERVICE_CATEGORIES
            )
            predicates.append(f"d.primary_category IN ({service_sql})")
        sql = DUNE_OWNER_SQL.replace(
            "WHERE a.blockchain IN ({chains})",
            "WHERE " + " AND ".join(predicates),
        )
        source = "dune_owner_addresses"
    elif dataset == "labels":
        selected_categories = tuple(
            sorted({item.strip() for item in categories if item.strip()})
        )
        if not selected_categories:
            raise ValueError("labels dataset requires at least one category")
        category_sql = ", ".join(
            "'" + item.replace("'", "''") + "'" for item in selected_categories
        )
        predicates = [f"category IN ({category_sql})"]
        if not all_chains:
            predicates.append(f"blockchain IN ({quoted})")
        sql = DUNE_LABELS_SQL.format(
            where_clause="WHERE " + " AND ".join(predicates)
        )
        source = "dune_labels_addresses"
    else:
        raise ValueError(
            "dataset must be 'cex', 'owners', 'labels', 'contracts', or 'services'"
        )
    execution_id, rows = client.execute(sql)
    registry = _registry_from_rows(source, rows, execution_id)
    LocalLabelDatabase(database).import_registry(registry)
    return DuneSyncResult(
        dataset=dataset,
        execution_id=execution_id,
        fetched_rows=len(rows),
        imported_records=len(registry.records),
        snapshot_id=registry.snapshots[0].snapshot_id,
        database=database,
    )


def lookup_dune_deposit_address(
    *,
    client: DuneLabelClient,
    database: Path,
    chain: str,
    address: str,
) -> DuneSyncResult:
    """Query one EVM deposit address without downloading the bulk dataset."""
    normalized_chain = CHAIN_ALIASES.get(chain.strip().casefold(), chain.strip().casefold())
    normalized_address = normalize_label_address(normalized_chain, address)
    address_hex = normalized_address.removeprefix("0x")
    if normalized_chain not in EVM_CHAINS:
        raise ValueError("Dune deposit-address lookup currently supports EVM chains")
    if len(address_hex) != 40 or any(char not in "0123456789abcdef" for char in address_hex):
        raise ValueError("EVM deposit address must contain exactly 40 hexadecimal characters")
    sql = DUNE_DEPOSIT_LOOKUP_SQL.format(
        chain=normalized_chain.replace("'", "''"),
        address_hex=address_hex,
    )
    execution_id, rows = client.execute(sql)
    registry = _registry_from_rows("dune_cex_deposit_addresses", rows, execution_id)
    LocalLabelDatabase(database).import_registry(registry)
    return DuneSyncResult(
        dataset="deposit_lookup",
        execution_id=execution_id,
        fetched_rows=len(rows),
        imported_records=len(registry.records),
        snapshot_id=registry.snapshots[0].snapshot_id,
        database=database,
    )


def _registry_from_rows(
    source: str,
    rows: Iterable[Mapping[str, Any]],
    execution_id: str,
) -> MultiSourceLabelRegistry:
    materialized = [dict(row) for row in rows]
    imported_at = datetime.now(UTC)
    digest = hashlib.sha256(
        json.dumps(materialized, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()
    snapshot = LabelSnapshot(
        snapshot_id=f"{source}-{digest[:16]}",
        source=source,
        imported_at=imported_at,
        record_count=len(materialized),
        sha256=digest,
        notes=f"Dune execution {execution_id}",
    )
    records: list[SourceLabelRecord] = []
    for row in materialized:
        chain = CHAIN_ALIASES.get(
            str(row.get("blockchain") or "").strip().casefold(),
            str(row.get("blockchain") or "").strip().casefold(),
        )
        address = normalize_label_address(chain, _display_address(chain, row))
        if source == "dune_cex_addresses":
            label = str(row.get("cex_name") or "").strip()
            category = "exchange"
            subcategory = str(row.get("distinct_name") or "").strip() or None
            source_record_id = None
        elif source == "dune_cex_deposit_addresses":
            cex_name = str(row.get("cex_name") or "").strip()
            label = f"{cex_name} deposit candidate" if cex_name else ""
            category = "exchange_deposit_candidate"
            subcategory = (
                str(row.get("first_deposit_token_standard") or "").strip() or None
            )
            source_record_id = (
                str(row.get("deposit_unique_key") or "").strip() or None
            )
        elif source == "dune_owner_addresses":
            label = next(
                (
                    str(row.get(key) or "").strip()
                    for key in ("custody_owner", "account_owner", "contract_name")
                    if str(row.get(key) or "").strip()
                ),
                "",
            )
            raw_category = str(row.get("primary_category") or "unknown").casefold()
            category = CATEGORY_ALIASES.get(raw_category, raw_category)
            subcategory = str(row.get("contract_name") or "").strip() or None
            source_record_id = str(row.get("owner_key") or "").strip() or None
        else:
            label = str(row.get("name") or "").strip()
            raw_category = str(row.get("category") or "unknown").casefold()
            category = CATEGORY_ALIASES.get(raw_category, raw_category)
            subcategory = (
                str(row.get("label_type") or row.get("model_name") or "").strip()
                or None
            )
            source_record_id = str(row.get("model_name") or "").strip() or None
        if not chain or not address or not label:
            continue
        records.append(
            SourceLabelRecord(
                chain=chain,
                address=address,
                label=label,
                category=category,
                subcategory=subcategory,
                source=source,
                verification_status=(
                    "unverified_candidate"
                    if source == "dune_cex_deposit_addresses"
                    else "dune_curated"
                ),
                snapshot_id=snapshot.snapshot_id,
                source_record_id=source_record_id,
                source_evidence=(
                    str(
                        row.get("source_evidence")
                        or row.get("identifying_transaction")
                        or ""
                    ).strip()
                    or None
                ),
                source_website=str(row.get("source_website") or "").strip() or None,
                confidence="high" if source == "dune_cex_addresses" else "medium",
                updated_at=_parse_datetime(
                    row.get("updated_at")
                    or row.get("added_date")
                    or row.get("consolidation_first_block_time")
                    or row.get("deposit_first_block_time")
                ),
                imported_at=imported_at,
            )
        )
    return MultiSourceLabelRegistry(records, (snapshot,))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith(" UTC"):
        text = text[:-4] + "+00:00"
    elif text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _display_address(chain: str, row: Mapping[str, Any]) -> str:
    direct = str(row.get("address") or "").strip()
    if direct:
        return direct
    encoded = str(row.get("address_hex") or "").strip()
    if encoded.startswith("0x"):
        encoded = encoded[2:]
    if not encoded:
        return ""
    if chain in EVM_CHAINS:
        return f"0x{encoded.casefold()}"
    try:
        decoded = bytes.fromhex(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return f"0x{encoded.casefold()}"
    return decoded


def _row_record(row: sqlite3.Row) -> SourceLabelRecord:
    payload = dict(row)
    for key in ("first_seen_at", "updated_at", "imported_at"):
        payload[key] = _parse_datetime(payload.get(key))
    return SourceLabelRecord(**payload)
