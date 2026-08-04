from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.providers.collector import CollectionResult


def write_provider_outputs(
    output_dir: Path,
    collection: CollectionResult,
    *,
    rejected_records: tuple[Any, ...] = (),
    analysis_completeness: str = "complete",
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    exporter = AnalysisExporter()
    status_path = output_dir / "provider_status.json"
    errors_path = output_dir / "provider_errors.json"
    rejected_path = output_dir / "rejected_records.json"
    status = []
    for index, result in enumerate(collection.results):
        later = [
            candidate
            for candidate in collection.results[index + 1 :]
            if candidate.capability is result.capability
        ]
        final = later[-1] if later else result
        pagination = asdict(result.pagination) if result.pagination else None
        status.append({
            "provider": result.provider,
            "chain": result.chain.value,
            "capability": result.capability.value,
            "fetched_at": result.fetched_at.isoformat(),
            "completeness": result.completeness.value,
            "warnings": list(result.warnings),
            "missing_data": list(result.missing_data),
            "status": result.completeness.value,
            "fallback_attempted": bool(later),
            "fallback_result": later[-1].completeness.value if later else None,
            "final_completeness": final.completeness.value,
            "truncated": result.truncated,
            "truncation_reason": result.truncation_reason,
            "fetched_records": result.fetched_records or len(result.records),
            "available_more": result.available_more,
            "analysis_completeness": analysis_completeness,
            "pagination": pagination,
        }
        )
    exporter.write_json(status_path, status)
    safe_errors = []
    seen_errors: set[int] = set()
    for error in collection.errors:
        if id(error) in seen_errors:
            continue
        seen_errors.add(id(error))
        later = [
            result
            for result in collection.results
            if result.capability is error.capability and result.provider != error.provider
        ]
        safe = error.to_safe_dict()
        safe.update(
            {
                "error_type": type(error).__name__,
                "fallback_attempted": bool(later),
                "resolved_by_fallback": any(
                    result.records and not result.missing_data for result in later
                ),
            }
        )
        safe_errors.append(safe)
    exporter.write_json(errors_path, safe_errors)
    exporter.write_json(rejected_path, rejected_records)
    grouped: dict[str, list[Any]] = {}
    for record in collection.records:
        grouped.setdefault(record.source_provider, []).append(record)
    for provider, records in grouped.items():
        exporter.write_json(raw_dir / f"{provider}.json", records)
    return {
        "provider_status": status_path,
        "provider_errors": errors_path,
        "rejected_records": rejected_path,
    }
