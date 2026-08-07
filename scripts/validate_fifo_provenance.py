"""Run a bounded, transaction-level FIFO provenance validation.

Generated artifacts contain case addresses and transaction hashes and therefore
belong under an ignored output/work directory. Provider credentials are read
only from the environment and are never serialized.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import httpx

from crypto_investigator.domain.fund_tracing import AllocationMethod, TraceEdge
from crypto_investigator.domain.lot_provenance import trace_fifo_provenance
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.tron.trongrid import TronGridProvider


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_address")
    parser.add_argument("addresses", nargs="+")
    parser.add_argument("--asset", default="USDT")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--min-amount", type=Decimal, default=Decimal("1"))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _edge(record) -> TraceEdge | None:
    if (
        not record.tx_hash
        or not record.from_address
        or not record.to_address
        or not record.timestamp
        or not record.amount_raw
        or record.decimals is None
        or record.success is False
    ):
        return None
    amount = Decimal(record.amount_raw) / (Decimal(10) ** record.decimals)
    reference = record.raw_reference or record.tx_hash
    return TraceEdge(
        edge_id=reference,
        from_address=record.from_address,
        to_address=record.to_address,
        transaction_hash=record.tx_hash,
        asset=record.asset_symbol or "unknown",
        amount=amount,
        timestamp=record.timestamp,
        allocation_method=AllocationMethod.DIRECT_TRANSACTION,
        confidence=Decimal("1"),
        evidence_refs=(f"TRONGRID:{reference}",),
    )


def _public(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_public(item) for item in value]
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items()}
    return value


async def _run(args: argparse.Namespace) -> dict:
    api_key = os.getenv("TRONGRID_API_KEY", "")
    if not api_key:
        raise RuntimeError("TRONGRID_API_KEY is not configured")
    request_count = 0

    async def count_request(_request: httpx.Request) -> None:
        nonlocal request_count
        request_count += 1

    transport = httpx.AsyncClient(event_hooks={"request": [count_request]})
    client = ProviderHttpClient(
        provider="trongrid",
        chain=Chain.TRON,
        retries=1,
        client=transport,
    )
    provider = TronGridProvider(api_key, client=client)
    started = perf_counter()
    results = {}
    try:
        for address in dict.fromkeys((args.seed_address, *args.addresses)):
            results[address] = await provider.get_token_transfers(
                address, unbounded=True
            )
    finally:
        await client.close()

    edges_by_id = {}
    status = {}
    for address, result in results.items():
        status[address] = {
            "records": len(result.records),
            "pages": result.pages_fetched,
            "completeness": result.completeness.value,
            "pagination_complete": bool(
                result.pagination and result.pagination.pagination_complete
            ),
            "warnings": list(result.warnings),
        }
        for record in result.records:
            if record.asset_symbol != args.asset:
                continue
            edge = _edge(record)
            if edge is not None:
                edges_by_id[edge.edge_id] = edge

    complete = frozenset(
        address
        for address in args.addresses
        if status[address]["pagination_complete"]
    )
    result = trace_fifo_provenance(
        seed_address=args.seed_address,
        edges=tuple(edges_by_id.values()),
        max_depth=args.max_depth,
        min_material_amount=args.min_amount,
        complete_addresses=complete,
    )
    seed_total = sum(
        (
            edge.amount
            for edge in edges_by_id.values()
            if edge.from_address == args.seed_address
            and edge.asset == args.asset
            and edge.amount >= args.min_amount
        ),
        Decimal("0"),
    )
    first_hop_allocated = sum(
        (item.amount for item in result.slices if item.hop == 1),
        Decimal("0"),
    )
    destination_totals: Counter[str] = Counter()
    for item in result.slices:
        if item.hop == 1:
            destination_totals[item.next_address] += item.amount
    return {
        "schema_version": 1,
        "mode": "transaction_level_fifo_validation",
        "asset": args.asset,
        "max_depth": args.max_depth,
        "min_material_amount": args.min_amount,
        "provider_calls": request_count,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "provider_status": status,
        "seed_total": seed_total,
        "first_hop_allocated": first_hop_allocated,
        "first_hop_unallocated": seed_total - first_hop_allocated,
        "conservation_passed": first_hop_allocated <= seed_total,
        "top_attributable_destinations": [
            {"address": address, "amount": amount}
            for address, amount in destination_totals.most_common(20)
        ],
        "slices": [asdict(item) for item in result.slices],
        "stops": [asdict(item) for item in result.stops],
        "rejected_edge_ids": result.rejected_edge_ids,
    }


def main() -> int:
    args = _arguments()
    payload = asyncio.run(_run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_public(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "provider_calls": payload["provider_calls"],
                "seed_total": str(payload["seed_total"]),
                "first_hop_allocated": str(payload["first_hop_allocated"]),
                "conservation_passed": payload["conservation_passed"],
                "output": args.output.name,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
