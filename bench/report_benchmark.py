from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
from time import perf_counter
import tracemalloc

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.domain.transaction import Chain, Transaction
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.models import GraphFilterOptions
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.evidence import EvidenceManifest
from crypto_investigator.reports.export import ReportExportCoordinator


TARGET = "0x" + "a" * 40


def transactions(count: int):
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(
        Transaction(
            chain=Chain.ETHEREUM,
            tx_hash=f"0x{index:064x}",
            from_address=TARGET if index % 2 else f"0x{index % 1000:040x}",
            to_address=f"0x{index % 1000:040x}" if index % 2 else TARGET,
            asset_symbol=("USDT", "ETH")[index % 2],
            amount=Decimal(index + 1) / Decimal("1000000"),
            timestamp=start + timedelta(minutes=index),
        )
        for index in range(count)
    )


def run_case(name: str, count: int, root: Path):
    analysis = AnalysisEngine().analyze(transactions(count), TARGET)
    graph = GraphBuilder().build(
        analysis,
        chain=Chain.ETHEREUM,
        target_address=TARGET,
        options=GraphFilterOptions(
            top_counterparties=20, maximum_nodes=30, maximum_edges=50
        ),
    )
    case = root / name
    case.mkdir(parents=True, exist_ok=True)
    source = case / "source_reference.txt"
    source.write_text(str(count), encoding="utf-8")
    timings = {}
    tracemalloc.start()
    started = perf_counter()
    evidence = EvidenceManifest().collect((source,), root=case)
    timings["evidence_manifest_seconds"] = perf_counter() - started
    started = perf_counter()
    document = ReportComposer().compose(
        analysis, graph=graph, target_address=TARGET, chain="ethereum", evidence=evidence
    )
    timings["composition_seconds"] = perf_counter() - started
    for report_format in ("markdown", "html", "docx", "pdf"):
        started = perf_counter()
        result = ReportExportCoordinator().export(document, case, report_format)
        timings[f"{report_format}_seconds"] = perf_counter() - started
        timings[f"{report_format}_status"] = result.status
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "transactions": count,
        **timings,
        "peak_memory_bytes": peak,
        "output_sizes": {
            path.name: path.stat().st_size
            for path in sorted(case.glob("report.*"))
        },
    }


if __name__ == "__main__":
    output = Path("bench/v6_report_output")
    output.mkdir(parents=True, exist_ok=True)
    results = {
        name: run_case(name, count, output)
        for name, count in (("small", 100), ("medium", 10_000), ("large", 100_000))
    }
    Path("bench/v6_report_benchmark.json").write_text(
        json.dumps(
            {
                "python_version": os.sys.version.split()[0],
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
