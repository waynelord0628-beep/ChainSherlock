from __future__ import annotations

import json
from uuid import uuid4

from crypto_investigator.cases import AuditLog, CaseRepository
from crypto_investigator.cases.results import CaseResult
from crypto_investigator.cases.storage import atomic_write_json
from crypto_investigator.reports.export import ReportExportCoordinator
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)
from crypto_investigator.services.case_narrative_service import (
    CaseNarrativeResult,
    CaseNarrativeService,
)


class CaseReportService:
    FILE_NAMES = {
        "report.md": "case_report.md",
        "report.html": "case_report.html",
        "report.docx": "case_report.docx",
        "report.pdf": "case_report.pdf",
        "report_data.json": "case_report_data.json",
        "evidence_manifest.json": "case_evidence_manifest.json",
        "export_status.json": "case_export_status.json",
        "export_errors.json": "case_export_errors.json",
    }

    def __init__(self, repository: CaseRepository) -> None:
        self.repository = repository

    def compose_document(
        self, result: CaseResult, narrative: CaseNarrativeResult | None = None
    ) -> ReportDocument:
        narrative = narrative or CaseNarrativeService().compose(result)
        sections = [
            ReportSection(
                section.section_id,
                section.title,
                index,
                tuple(section.paragraphs),
            )
            for index, section in enumerate(narrative.sections, 1)
        ]
        sections.extend(
            [
                ReportSection(
                    "evidence_index",
                    "Evidence Index",
                    len(sections) + 1,
                    tables=(
                        ReportTable(
                            "evidence_table",
                            "Evidence Index",
                            ("ID", "Type", "Path", "SHA-256", "Integrity"),
                            tuple(
                                (
                                    item.evidence_id,
                                    item.evidence_type,
                                    item.relative_path,
                                    item.sha256 or "unavailable",
                                    item.integrity_status,
                                )
                                for item in result.evidence_index
                            ),
                        ),
                    ),
                    evidence_refs=tuple(
                        item.evidence_id for item in result.evidence_index
                    ),
                ),
                ReportSection(
                    "audit_summary",
                    "Audit Summary",
                    len(sections) + 2,
                    (
                        f"Entries: {result.audit_summary.entry_count}",
                        f"Hash chain integrity: {result.audit_summary.chain_integrity}",
                    ),
                ),
                ReportSection(
                    "review_status",
                    "Review Status",
                    len(sections) + 3,
                    ("not_reviewed",),
                ),
            ]
        )
        evidence = tuple(
            ReportEvidence(
                evidence_id=item.evidence_id,
                evidence_type=item.evidence_type,
                source=item.source,
                source_reference=item.relative_path,
                description=item.description,
                collected_at=item.created_at,
                hash=item.sha256,
            )
            for item in result.evidence_index
        )
        limitations = tuple(
            ReportLimitation(f"case_limit_{index}", text)
            for index, text in enumerate(result.limitations, 1)
        )
        warnings = tuple(
            ReportWarning("case_warning", item) for item in result.warnings
        )
        return ReportDocument(
            title=f"ChainSherlock Case Investigation Report: {result.title}",
            metadata=ReportMetadata(
                report_id=f"CASE-{uuid4().hex[:12].upper()}",
                report_version="8",
                analysis_completeness=result.completeness,
                graph_completeness=result.completeness,
                warning_count=len(warnings),
                transaction_count=sum(
                    int(item.get("transaction_count", 0))
                    for item in result.address_results
                ),
            ),
            sections=tuple(sections),
            evidence=evidence,
            citations=(),
            warnings=warnings,
            limitations=limitations,
            conclusion=ReportConclusion(
                completeness=result.completeness,
                text=(
                    "本報告不構成對身分、犯罪、詐欺或洗錢的確定性判斷。"
                    "This conclusion separates confirmed facts, deterministic "
                    "observations, and candidate interpretations. It does not make "
                    "a definitive finding of identity, crime, fraud, or money laundering."
                ),
            ),
        )

    def generate(self, result: CaseResult, requested_format: str = "all") -> dict:
        workspace = self.repository.workspace(result.case_id)
        reports_root = workspace.resolve_relative("reports")
        reports_root.mkdir(exist_ok=True)
        existing = sorted(
            item
            for item in reports_root.iterdir()
            if item.is_dir() and item.name.startswith("v")
        )
        version = len(existing) + 1
        output = reports_root / f"v{version:03d}"
        document = self.compose_document(result)
        exported = ReportExportCoordinator().export(
            document, output, requested_format
        )
        files = {}
        for original, renamed in self.FILE_NAMES.items():
            source = output / original
            if source.exists():
                destination = output / renamed
                source.replace(destination)
                files[renamed] = str(
                    destination.relative_to(workspace.path).as_posix()
                )
        summary = {
            "report_version": version,
            "status": exported.status,
            "files": files,
            "created_at": document.metadata.generated_at.isoformat(),
        }
        atomic_write_json(output / "case_report_version.json", summary)
        AuditLog(workspace).append(
            action="report_created",
            object_type="case_report",
            object_id=f"report_v{version:03d}",
            description="Case report created",
            metadata={"version": version, "status": exported.status},
        )
        return summary

    def list_reports(self, case_id: str) -> tuple[dict, ...]:
        root = self.repository.workspace(case_id).resolve_relative("reports")
        if not root.exists():
            return ()
        return tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(root.glob("v*/case_report_version.json"))
        )

    def latest_report(self, case_id: str) -> dict | None:
        reports = self.list_reports(case_id)
        return reports[-1] if reports else None
