"""Deterministic V6.5 Investigation Feature Engine benchmark."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
from time import perf_counter
import tracemalloc
from types import SimpleNamespace

from crypto_investigator.investigation import InvestigationFeatureEngine


TARGET = "0x" + "a" * 40


def fixture(size: int, completeness: str):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    edges = []
    counts = {}
    for index in range(size):
        counterparty = f"0x{index % 1000:040x}"
        incoming = index % 2 == 0
        source, target = (
            (counterparty, TARGET) if incoming else (TARGET, counterparty)
        )
        edges.append(
            SimpleNamespace(
                source=source,
                target=target,
                direction="incoming" if incoming else "outgoing",
                weight=Decimal(index % 100 + 1),
                asset="USDT" if index % 3 else "TRX",
                timestamp=start + timedelta(minutes=index),
                tx_hash=f"0x{index:064x}",
            )
        )
        counts[counterparty] = counts.get(counterparty, 0) + 1
    counterparties = tuple(
        SimpleNamespace(
            address=address,
            interaction_count=count,
            incoming_count=count,
            outgoing_count=0,
        )
        for address, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    )
    return SimpleNamespace(
        flow=SimpleNamespace(edges=tuple(edges)),
        counterparties=counterparties,
        statistics=SimpleNamespace(transaction_frequency=Decimal("1")),
        metadata={"chain": "ethereum", "completeness": completeness},
    )


def run(size: int, completeness: str):
    analysis = fixture(size, completeness)
    tracemalloc.start()
    started = perf_counter()
    result = InvestigationFeatureEngine().analyze(analysis, TARGET)
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "transactions": size,
        "completeness": completeness,
        "seconds": round(elapsed, 6),
        "peak_memory_mib": round(peak / 1024 / 1024, 3),
        "observations": len(result.observations),
        "evidence_refs": len(result.evidence_refs),
    }


if __name__ == "__main__":
    results = [
        run(100, "complete"),
        run(10_000, "complete"),
        run(100_000, "complete"),
        run(10_000, "partial"),
    ]
    output = Path("bench/v65_investigation_benchmark.json")
    output.write_text(
        json.dumps(
            {
                "python": __import__("platform").python_version(),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output)
