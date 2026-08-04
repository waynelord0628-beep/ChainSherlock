from typing import Hashable, Iterable

from crypto_investigator.providers.models import ProviderRawRecord


def record_key(record: ProviderRawRecord) -> tuple[Hashable, ...]:
    base = (record.chain.value, record.tx_hash, record.source_type)
    if record.source_type == "token_transfer":
        return base + (
            record.metadata.get("log_index"),
            record.asset_contract,
        )
    if record.source_type == "internal_transfer":
        return base + (record.metadata.get("trace_id"),)
    if record.source_type in ("bitcoin_input", "bitcoin_output"):
        return base + (
            record.metadata.get("input_index", record.metadata.get("output_index")),
            record.from_address or record.to_address,
            record.amount_raw,
        )
    return base


def deduplicate_records(
    records: Iterable[ProviderRawRecord],
) -> tuple[ProviderRawRecord, ...]:
    deduplicated: list[ProviderRawRecord] = []
    seen: set[tuple[Hashable, ...]] = set()
    for record in records:
        key = record_key(record)
        if key not in seen:
            seen.add(key)
            deduplicated.append(record)
    return tuple(deduplicated)
