"""Offline V5 Graph benchmark with bounded rendered output."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.domain.transaction import Chain, Transaction
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.filtering import GraphFilter
from crypto_investigator.graphs.graphml_exporter import GraphMLExporter
from crypto_investigator.graphs.html_renderer import HtmlGraphRenderer
from crypto_investigator.graphs.json_exporter import JsonGraphExporter
from crypto_investigator.graphs.models import GraphFilterOptions
from crypto_investigator.graphs.networkx_adapter import NetworkXAdapter


TARGET = "0x" + "a" * 40


def fixture(size: int) -> tuple[Transaction, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(
        Transaction(
            chain=Chain.ETHEREUM,
            tx_hash=f"0x{index:064x}",
            from_address=TARGET if index % 2 == 0 else f"0x{index % 200:040x}",
            to_address=f"0x{index % 200:040x}" if index % 2 == 0 else TARGET,
            asset_symbol=("ETH", "USDT", "USDC")[index % 3],
            amount=Decimal(index + 1) / Decimal("100"),
            timestamp=start + timedelta(seconds=index),
        )
        for index in range(size)
    )


def timed(action):
    started = perf_counter()
    result = action()
    return result, perf_counter() - started


def run(size: int) -> dict[str, float]:
    analysis = AnalysisEngine().analyze(fixture(size), TARGET)
    broad = GraphFilterOptions(
        top_counterparties=1000, maximum_nodes=1000, maximum_edges=1000
    )
    safe = GraphFilterOptions(maximum_nodes=100, maximum_edges=200)
    tracemalloc.start()
    graph, build = timed(
        lambda: GraphBuilder().build(
            analysis,
            chain=Chain.ETHEREUM,
            target_address=TARGET,
            options=broad,
        )
    )
    filtered, filtering = timed(lambda: GraphFilter().apply(graph, safe))
    _, networkx_time = timed(lambda: NetworkXAdapter().convert(filtered))
    with TemporaryDirectory() as directory:
        root = Path(directory)
        json_path = root / "flow_graph.json"
        graphml_path = root / "flow.graphml"
        html_path = root / "flow.html"
        _, json_time = timed(lambda: JsonGraphExporter().write(filtered, json_path))
        _, graphml_time = timed(
            lambda: GraphMLExporter().write(filtered, graphml_path)
        )
        _, html_time = timed(lambda: HtmlGraphRenderer().write(filtered, html_path))
        output_bytes = sum(
            path.stat().st_size for path in (json_path, graphml_path, html_path)
        )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "build": build,
        "filter": filtering,
        "networkx": networkx_time,
        "json": json_time,
        "graphml": graphml_time,
        "html": html_time,
        "peak_mib": peak / 1024 / 1024,
        "output_kib": output_bytes / 1024,
    }


if __name__ == "__main__":
    print(
        "records,build_s,filter_s,networkx_s,json_s,graphml_s,html_s,"
        "peak_mib,output_kib"
    )
    for count in (100, 10_000, 100_000):
        result = run(count)
        print(
            f"{count},{result['build']:.4f},{result['filter']:.4f},"
            f"{result['networkx']:.4f},{result['json']:.4f},"
            f"{result['graphml']:.4f},{result['html']:.4f},"
            f"{result['peak_mib']:.2f},{result['output_kib']:.2f}"
        )
