from __future__ import annotations

from dataclasses import dataclass

from crypto_investigator.cases import CaseRecord


@dataclass(frozen=True, slots=True)
class CaseViewModel:
    case_id: str
    title: str
    status: str
    updated_at: str
    evidence_count: int
    execution_status: str

    @classmethod
    def from_record(cls, record: CaseRecord) -> "CaseViewModel":
        return cls(
            case_id=record.case_id,
            title=record.title,
            status=record.status.value,
            updated_at=record.updated_at.isoformat(),
            evidence_count=len(record.evidence),
            execution_status=record.last_execution_status or "not_started",
        )
