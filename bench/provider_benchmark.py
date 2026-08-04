"""Repeatable, offline V4 Provider fixture benchmark."""

from datetime import UTC, datetime, timedelta
from time import perf_counter
import tracemalloc

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.core.pipeline import DataPipeline
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.importers.provider import ProviderRecordImporter
from crypto_investigator.providers.dedup import deduplicate_records
from crypto_investigator.providers.models import ProviderRawRecord


def fixture(size: int) -> tuple[ProviderRawRecord, ...]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return tuple(
        ProviderRawRecord(
            chain=Chain.ETHEREUM,
            source_provider="mock",
            source_type="normal_transaction",
            tx_hash=f"0x{index:064x}",
            timestamp=start + timedelta(seconds=index),
            from_address="0x" + "1" * 40,
            to_address="0x" + "2" * 40,
            asset_symbol="ETH",
            amount_raw=str(index + 1),
            decimals=18,
            transaction_type="native_transfer",
        )
        for index in range(size)
    )


def timed(action):
    started = perf_counter()
    value = action()
    return value, perf_counter() - started


def run(size: int) -> dict[str, float]:
    tracemalloc.start()
    records, fetch = timed(lambda: fixture(size))
    parsed, parsing = timed(lambda: tuple(records))
    unique, dedup = timed(lambda: deduplicate_records(parsed))
    transactions, pipeline = timed(
        lambda: DataPipeline().to_domain(ProviderRecordImporter().load(unique))
    )
    _, analysis = timed(lambda: AnalysisEngine().analyze(transactions))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "fetch": fetch,
        "parsing": parsing,
        "dedup": dedup,
        "pipeline": pipeline,
        "analysis": analysis,
        "peak_mib": peak / 1024 / 1024,
    }


if __name__ == "__main__":
    print("records,fetch_s,parsing_s,dedup_s,pipeline_s,analysis_s,peak_mib")
    for count in (100, 10_000, 100_000):
        result = run(count)
        print(
            f"{count},{result['fetch']:.4f},{result['parsing']:.4f},"
            f"{result['dedup']:.4f},{result['pipeline']:.4f},"
            f"{result['analysis']:.4f},{result['peak_mib']:.2f}"
        )
