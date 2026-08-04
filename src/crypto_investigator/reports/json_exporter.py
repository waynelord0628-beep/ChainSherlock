from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from crypto_investigator.reports.models import (
    ReportCitation,
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportFigure,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def write_report_data(document: ReportDocument, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(document), ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    return path


def read_report_data(path: Path) -> ReportDocument:
    value = json.loads(path.read_text(encoding="utf-8"))

    def warning(item):
        return ReportWarning(**item)

    def limitation(item):
        return ReportLimitation(**item)

    def table(item):
        return ReportTable(
            **{
                **item,
                "columns": tuple(item["columns"]),
                "rows": tuple(tuple(row) for row in item["rows"]),
            }
        )

    def evidence(item):
        collected_at = item.get("collected_at")
        return ReportEvidence(
            **{
                **item,
                "collected_at": datetime.fromisoformat(collected_at) if collected_at else None,
            }
        )

    def section(item):
        return ReportSection(
            **{
                **item,
                "content_blocks": tuple(item["content_blocks"]),
                "tables": tuple(table(row) for row in item["tables"]),
                "figures": tuple(ReportFigure(**row) for row in item["figures"]),
                "evidence_refs": tuple(item["evidence_refs"]),
                "warnings": tuple(warning(row) for row in item["warnings"]),
                "limitations": tuple(limitation(row) for row in item["limitations"]),
                "claims": tuple(item.get("claims", ())),
                "fact_refs": tuple(item.get("fact_refs", ())),
                "observation_refs": tuple(item.get("observation_refs", ())),
            }
        )

    metadata = value["metadata"]
    metadata["generated_at"] = datetime.fromisoformat(metadata["generated_at"])
    metadata["source_files"] = tuple(metadata["source_files"])
    metadata["providers"] = tuple(metadata["providers"])
    return ReportDocument(
        title=value["title"],
        metadata=ReportMetadata(**metadata),
        sections=tuple(section(item) for item in value["sections"]),
        evidence=tuple(evidence(item) for item in value["evidence"]),
        citations=tuple(ReportCitation(**item) for item in value["citations"]),
        warnings=tuple(warning(item) for item in value["warnings"]),
        limitations=tuple(limitation(item) for item in value["limitations"]),
        conclusion=ReportConclusion(**value["conclusion"]),
    )
