from argparse import ArgumentParser
import gc
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.core.pipeline import DataPipeline

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
TARGET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
SIZES = {"small": 10, "medium": 1_000, "large": 10_000}


def generate_examples() -> None:
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    header = "from,to,amount,asset,timestamp,hash\n"
    for name, count in SIZES.items():
        rows = [header]
        for index in range(count):
            incoming = index % 2 == 0
            source, target = (OTHER, TARGET) if incoming else (TARGET, OTHER)
            asset = "USDT" if index % 3 == 0 else "ETH"
            amount = f"{(index % 100) + 1}.5"
            timestamp = (
                f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}"
                f"T{index % 24:02d}:00:00Z"
            )
            tx_hash = f"0x{index:064x}"
            rows.append(
                f"{source},{target},{amount},{asset},{timestamp},{tx_hash}\n"
            )
        (EXAMPLES / f"{name}.csv").write_text("".join(rows), encoding="utf-8")


def benchmark(path: Path) -> tuple[int, float, float]:
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    with TemporaryDirectory() as temporary:
        output_dir = Path(temporary)
        pipeline_result = DataPipeline().run(path, output_dir=output_dir / "pipeline")
        analysis_result = AnalysisEngine().analyze(
            pipeline_result.transactions, TARGET
        )
        AnalysisExporter().export_all(analysis_result, output_dir / "analysis")
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return len(pipeline_result.transactions), elapsed, peak / (1024 * 1024)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    arguments = parser.parse_args()
    if arguments.generate or any(
        not (EXAMPLES / f"{name}.csv").exists() for name in SIZES
    ):
        generate_examples()

    results = [
        (name, *benchmark(EXAMPLES / f"{name}.csv")) for name in SIZES
    ]
    lines = [
        "# V3 Analysis Engine Benchmark",
        "",
        f"- Python: {platform.python_version()}",
        f"- Platform: {platform.platform()}",
        "- Scope: Data Pipeline, Analysis Engine, and data-only export",
        "- Method: single measured run with `time.perf_counter` and `tracemalloc`",
        "",
        "| Dataset | Transactions | Execution Time (s) | Peak Memory (MiB) |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {name} | {count} | {elapsed:.4f} | {peak:.2f} |"
        for name, count, elapsed, peak in results
    )
    lines.extend(
        [
            "",
            "Results are environment-specific and are intended as a regression baseline.",
            "",
        ]
    )
    (ROOT / "bench" / "benchmark.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
