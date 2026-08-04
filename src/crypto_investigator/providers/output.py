from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.providers.collector import CollectionResult


def write_provider_outputs(
    output_dir: Path, collection: CollectionResult
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    exporter = AnalysisExporter()
    status_path = output_dir / "provider_status.json"
    errors_path = output_dir / "provider_errors.json"
    status = [
        {
            "provider": result.provider,
            "chain": result.chain.value,
            "capability": result.capability.value,
            "fetched_at": result.fetched_at.isoformat(),
            "completeness": result.completeness.value,
            "warnings": list(result.warnings),
            "missing_data": list(result.missing_data),
        }
        for result in collection.results
    ]
    exporter.write_json(status_path, status)
    exporter.write_json(
        errors_path, [error.to_safe_dict() for error in collection.errors]
    )
    grouped: dict[str, list[Any]] = {}
    for record in collection.records:
        grouped.setdefault(record.source_provider, []).append(record)
    for provider, records in grouped.items():
        exporter.write_json(raw_dir / f"{provider}.json", records)
    return {"provider_status": status_path, "provider_errors": errors_path}
