from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


TRON_USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def _amount(record: Mapping[str, Any]) -> Decimal:
    raw = Decimal(str(record.get("amount_raw", "0")))
    return raw / (Decimal(10) ** int(record.get("decimals") or 0))


def _timestamp(record: Mapping[str, Any]) -> datetime:
    value = str(record["timestamp"])
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _direction(record: Mapping[str, Any], target: str) -> str:
    if record.get("to_address") == target:
        return "incoming"
    if record.get("from_address") == target:
        return "outgoing"
    return "unclassified"


def _group_counterparties(
    records: Sequence[Mapping[str, Any]],
    target: str,
    direction: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        if _direction(record, target) != direction or _amount(record) <= 0:
            continue
        address = (
            str(record.get("from_address"))
            if direction == "incoming"
            else str(record.get("to_address"))
        )
        item = grouped.setdefault(
            address,
            {
                "address": address,
                "amount": Decimal("0"),
                "transaction_count": 0,
                "timestamps": [],
                "evidence_refs": [],
            },
        )
        item["amount"] += _amount(record)
        item["transaction_count"] += 1
        item["timestamps"].append(_timestamp(record))
        if record.get("tx_hash"):
            item["evidence_refs"].append(str(record["tx_hash"]))
    total = sum((item["amount"] for item in grouped.values()), Decimal("0"))
    ranked = sorted(
        grouped.values(),
        key=lambda item: (-item["amount"], -item["transaction_count"], item["address"]),
    )
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
        item["share"] = item["amount"] / total if total else Decimal("0")
        item["first_seen"] = min(item.pop("timestamps")).isoformat()
        item["last_seen"] = max(
            _timestamp(record)
            for record in records
            if (
                record.get("from_address")
                if direction == "incoming"
                else record.get("to_address")
            )
            == item["address"]
            and _amount(record) > 0
        ).isoformat()
        item["label"] = None
        item["label_source"] = None
        item["verification_status"] = "unverified"
    return ranked


def _shares(ranked: Sequence[Mapping[str, Any]], counts: Iterable[int]) -> dict[str, str]:
    return {
        f"top_{count}_share": str(
            sum((Decimal(str(item["share"])) for item in ranked[:count]), Decimal("0"))
        )
        for count in counts
    }


def _time_series(
    records: Sequence[Mapping[str, Any]], target: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    monthly: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"incoming": Decimal("0"), "outgoing": Decimal("0")}
    )
    daily: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"incoming": Decimal("0"), "outgoing": Decimal("0")}
    )
    for record in records:
        amount = _amount(record)
        if amount <= 0:
            continue
        direction = _direction(record, target)
        if direction not in {"incoming", "outgoing"}:
            continue
        timestamp = _timestamp(record)
        monthly[timestamp.strftime("%Y-%m")][direction] += amount
        daily[timestamp.strftime("%Y-%m-%d")][direction] += amount

    def rows(source):
        return [
            {
                "period": period,
                "incoming": str(values["incoming"]),
                "outgoing": str(values["outgoing"]),
                "net": str(values["incoming"] - values["outgoing"]),
            }
            for period, values in sorted(source.items())
        ]

    return rows(monthly), rows(daily)


def _adjacent_pairs(records: Sequence[Mapping[str, Any]], target: str) -> dict[str, Any]:
    nonzero = sorted(
        (record for record in records if _amount(record) > 0),
        key=_timestamp,
    )
    intervals: list[float] = []
    within_hour = 0
    within_day = 0
    for current, following in zip(nonzero, nonzero[1:]):
        if (
            _direction(current, target) == "incoming"
            and _direction(following, target) == "outgoing"
        ):
            seconds = (_timestamp(following) - _timestamp(current)).total_seconds()
            if seconds >= 0:
                intervals.append(seconds)
                within_hour += seconds <= 3600
                within_day += seconds <= 86400
    all_timestamps = [_timestamp(record) for record in nonzero]
    transaction_intervals = [
        (right - left).total_seconds()
        for left, right in zip(all_timestamps, all_timestamps[1:])
    ]
    return {
        "adjacent_inflow_outflow_pairs": len(intervals),
        "within_1_hour": within_hour,
        "within_24_hours": within_day,
        "median_transaction_interval_seconds": (
            str(median(transaction_intervals)) if transaction_intervals else None
        ),
        "limitation": (
            "相鄰流入後流出只代表時間接近，不代表同一筆資金已完成逐筆追蹤。"
        ),
    }


def _artifact_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_full_asset_benchmark(
    records: Sequence[Mapping[str, Any]],
    provider_status: Sequence[Mapping[str, Any]],
    *,
    target_address: str,
    raw_artifact: Path | None = None,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    usdt = [
        record
        for record in records
        if record.get("asset_symbol") == "USDT"
        and record.get("asset_contract") == TRON_USDT_CONTRACT
        and record.get("source_type") == "token_transfer"
    ]
    trx = [
        record
        for record in records
        if record.get("asset_symbol") == "TRX"
        and record.get("transaction_type") == "native_transfer"
        and (record.get("metadata") or {}).get("contract_type") == "TransferContract"
    ]
    other_assets = [
        record for record in records if record not in usdt and record not in trx
    ]
    incoming = [
        item for item in usdt
        if _direction(item, target_address) == "incoming" and _amount(item) > 0
    ]
    outgoing = [
        item for item in usdt
        if _direction(item, target_address) == "outgoing" and _amount(item) > 0
    ]
    zero_value = [item for item in usdt if _amount(item) == 0]
    sources = _group_counterparties(usdt, target_address, "incoming")
    destinations = _group_counterparties(usdt, target_address, "outgoing")
    incoming_addresses = {item["address"] for item in sources}
    outgoing_addresses = {item["address"] for item in destinations}
    incoming_total = sum((_amount(item) for item in incoming), Decimal("0"))
    outgoing_total = sum((_amount(item) for item in outgoing), Decimal("0"))
    monthly, daily = _time_series(usdt, target_address)
    active_days = len({_timestamp(item).date() for item in usdt})

    first_hop = [
        {
            "destination_address": item["address"],
            "received_usdt": str(item["amount"]),
            "transaction_count": item["transaction_count"],
            "share_of_usdt_outflow": str(item["share"]),
            "first_receipt": item["first_seen"],
            "last_receipt": item["last_seen"],
            "label_status": "unverified" if not item["label"] else "label_candidate",
            "onward_status": "not_collected",
            "priority": "high" if index < 5 else "medium",
            "priority_reasons": [
                "principal_value_asset",
                "received_amount_descending",
                "share_of_total_outflow",
            ],
            "evidence_refs": item["evidence_refs"],
        }
        for index, item in enumerate(destinations[:10])
    ]
    trx_incoming = [
        item for item in trx
        if _direction(item, target_address) == "incoming" and _amount(item) > 0
    ]
    trx_outgoing = [
        item for item in trx
        if _direction(item, target_address) == "outgoing" and _amount(item) > 0
    ]
    dust = [
        item for item in trx
        if _direction(item, target_address) == "incoming"
        and Decimal("0") < _amount(item) < Decimal("0.0001")
    ]
    statuses = {
        str(item.get("capability")): item for item in provider_status
        if item.get("capability")
    }
    required = ("address_transactions", "token_transfers")
    full_history_complete = all(
        statuses.get(capability, {}).get("final_completeness") == "complete"
        and statuses.get(capability, {}).get("pagination", {}).get(
            "pagination_complete"
        )
        and not statuses.get(capability, {}).get("truncated")
        for capability in required
    )
    request_pages = {
        capability: (
            int(statuses[capability].get("fetched_records", 0)) + 199
        ) // 200
        for capability in required
        if capability in statuses
    }
    result = {
        "benchmark_version": "1",
        "target_address": target_address,
        "chain": "tron",
        "scope_type": "full_history",
        "full_history_complete": full_history_complete,
        "required_capabilities": {
            capability: {
                "complete": statuses.get(capability, {}).get(
                    "final_completeness"
                )
                == "complete",
                "fetched_records": int(
                    statuses.get(capability, {}).get("fetched_records", 0)
                ),
                "accepted_records": int(
                    statuses.get(capability, {})
                    .get("pagination", {})
                    .get("accepted_records", 0)
                ),
                "rejected_records": int(
                    statuses.get(capability, {})
                    .get("pagination", {})
                    .get("rejected_records", 0)
                ),
                "deduplicated_records": int(
                    statuses.get(capability, {})
                    .get("pagination", {})
                    .get("deduplicated_records", 0)
                ),
                "pages": request_pages.get(capability, 0),
            }
            for capability in required
        },
        "provider_usage": {
            "request_count": sum(request_pages.values()),
            "page_count": sum(request_pages.values()),
            "rate_limit_responses": 0,
            "elapsed_seconds": elapsed_seconds,
        },
        "asset_priority": [
            {
                "asset": "USDT",
                "role": "principal_value_asset",
                "reason": "highest economic throughput and material value flow",
            },
            {
                "asset": "TRX",
                "role": "operational_asset",
                "reason": "native operational and fee asset with lower throughput",
            },
            {
                "asset": "OTHER",
                "role": "spam_or_low_materiality_asset",
                "reason": "separately classified non-core assets",
            },
        ],
        "usdt": {
            "contract": TRON_USDT_CONTRACT,
            "decimals": 6,
            "first_seen": min(map(_timestamp, usdt)).isoformat() if usdt else None,
            "last_seen": max(map(_timestamp, usdt)).isoformat() if usdt else None,
            "transaction_count": len(usdt),
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "zero_value_count": len(zero_value),
            "incoming_total": str(incoming_total),
            "outgoing_total": str(outgoing_total),
            "bidirectional_volume": str(incoming_total + outgoing_total),
            "net_flow": str(incoming_total - outgoing_total),
            "unique_incoming_counterparties": len(incoming_addresses),
            "unique_outgoing_counterparties": len(outgoing_addresses),
            "bidirectional_counterparties": len(
                incoming_addresses & outgoing_addresses
            ),
            "total_nonzero_counterparties": len(
                incoming_addresses | outgoing_addresses
            ),
            "active_days": active_days,
            "source_concentration": _shares(sources, (1, 5, 10)),
            "destination_concentration": _shares(destinations, (1, 5, 10)),
            "top_incoming_sources": sources[:10],
            "top_outgoing_destinations": destinations[:10],
            "monthly": monthly,
            "daily": daily,
            "timing": _adjacent_pairs(usdt, target_address),
        },
        "trx": {
            "transaction_count": len(trx),
            "incoming_count": len(trx_incoming),
            "outgoing_count": len(trx_outgoing),
            "incoming_total": str(
                sum((_amount(item) for item in trx_incoming), Decimal("0"))
            ),
            "outgoing_total": str(
                sum((_amount(item) for item in trx_outgoing), Decimal("0"))
            ),
            "micro_dust_excluded_count": len(dust),
            "micro_dust_excluded_amount": str(
                sum((_amount(item) for item in dust), Decimal("0"))
            ),
        },
        "other_asset_record_count": len(other_assets),
        "first_hop_candidates": first_hop,
        "labels": {
            "applied_count": 0,
            "status": "unverified",
            "note": "No matching Local Label artifact was supplied.",
        },
        "evidence_lineage": {
            "raw_artifact": raw_artifact.name if raw_artifact else None,
            "raw_artifact_sha256": (
                _artifact_hash(raw_artifact)
                if raw_artifact and raw_artifact.exists()
                else None
            ),
        },
    }
    return result


def benchmark_reconciliation(
    result: Mapping[str, Any],
    reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare an explicitly supplied external reference without runtime coupling."""
    baseline = dict(reference or {})
    usdt = result["usdt"]
    actual = {
        **{
            key: usdt[key]
            for key in (
                "transaction_count",
                "incoming_count",
                "outgoing_count",
                "zero_value_count",
                "incoming_total",
                "outgoing_total",
                "bidirectional_volume",
                "net_flow",
                "total_nonzero_counterparties",
            )
        },
        "top_1_source_share": usdt["source_concentration"]["top_1_share"],
        "top_5_source_share": usdt["source_concentration"]["top_5_share"],
        "top_1_destination_share": usdt["destination_concentration"]["top_1_share"],
        "top_5_destination_share": usdt["destination_concentration"]["top_5_share"],
    }
    comparisons = []
    for key, expected in baseline.items():
        value = actual[key]
        if isinstance(expected, Decimal):
            numeric = Decimal(str(value))
            difference = numeric - expected
            matches = abs(difference) <= Decimal("0.01")
        else:
            difference = int(value) - expected
            matches = difference == 0
        comparisons.append(
            {
                "metric": key,
                "actual": str(value),
                "reference": str(expected),
                "difference": str(difference),
                "matches_tolerance": matches,
            }
        )
    return {
        "reference_is_external_comparison_only": bool(reference),
        "reference_supplied": bool(reference),
        "all_core_counts_match": all(
            item["matches_tolerance"]
            for item in comparisons
            if item["metric"] in {
                "transaction_count",
                "incoming_count",
                "outgoing_count",
                "zero_value_count",
            }
        ),
        "comparisons": comparisons,
        "possible_difference_reasons": [
            "provider cutoff time",
            "zero-value event treatment",
            "label source availability",
            "rounding of displayed percentages",
        ],
    }


def write_full_asset_benchmark(
    result: Mapping[str, Any], output_directory: Path
) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    benchmark_path = output_directory / "full_asset_benchmark.json"
    benchmark_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    reconciliation_path = output_directory / "benchmark_reconciliation.json"
    reconciliation_path.write_text(
        json.dumps(
            benchmark_reconciliation(result),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    candidates_path = output_directory / "first_hop_candidates.csv"
    with candidates_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "destination_address",
                "received_usdt",
                "transaction_count",
                "share_of_usdt_outflow",
                "first_receipt",
                "last_receipt",
                "label_status",
                "onward_status",
                "priority",
                "priority_reasons",
                "evidence_refs",
            )
        )
        for item in result["first_hop_candidates"]:
            writer.writerow(
                (
                    item["destination_address"],
                    item["received_usdt"],
                    item["transaction_count"],
                    item["share_of_usdt_outflow"],
                    item["first_receipt"],
                    item["last_receipt"],
                    item["label_status"],
                    item["onward_status"],
                    item["priority"],
                    "|".join(item["priority_reasons"]),
                    "|".join(item["evidence_refs"]),
                )
            )
    return {
        "benchmark": benchmark_path,
        "reconciliation": reconciliation_path,
        "first_hop_candidates": candidates_path,
    }
