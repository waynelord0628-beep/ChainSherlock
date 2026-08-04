import json
from pathlib import Path

from crypto_investigator.reports.docx_exporter import DocxReportExporter
from crypto_investigator.reports.evidence import EvidenceManifest
from crypto_investigator.reports.errors import ReportExportError
from crypto_investigator.reports.formatting import safe_output_path, validate_output_directory
from crypto_investigator.reports.html_exporter import HtmlReportExporter
from crypto_investigator.reports.json_exporter import write_report_data
from crypto_investigator.reports.markdown_exporter import MarkdownReportExporter
from crypto_investigator.reports.models import ReportDocument, ReportExportResult
from crypto_investigator.reports.pdf_exporter import PdfReportExporter


class ReportExportCoordinator:
    exporters = {
        "markdown": ("report.md", MarkdownReportExporter),
        "html": ("report.html", HtmlReportExporter),
        "docx": ("report.docx", DocxReportExporter),
        "pdf": ("report.pdf", PdfReportExporter),
    }

    def export(
        self,
        document: ReportDocument,
        output_directory: Path,
        requested_format: str = "all",
    ) -> ReportExportResult:
        root = validate_output_directory(output_directory)
        root.mkdir(parents=True, exist_ok=True)
        selected = tuple(self.exporters) if requested_format == "all" else (requested_format,)
        if any(item not in self.exporters for item in selected):
            raise ReportExportError("Unsupported report format")

        files = {}
        errors = []
        data_path = write_report_data(document, safe_output_path(root, "report_data.json"))
        files["report_data"] = data_path.name
        manifest_path = EvidenceManifest().write(
            document.evidence, safe_output_path(root, "evidence_manifest.json")
        )
        files["evidence_manifest"] = manifest_path.name

        for name in selected:
            filename, exporter_type = self.exporters[name]
            try:
                path = exporter_type().write(document, safe_output_path(root, filename))
                files[name] = path.name
            except ReportExportError as error:
                errors.append(
                    {
                        "format": name,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )

        successful_formats = sum(name in files for name in selected)
        status = "complete" if not errors else ("partial" if successful_formats else "failed")
        error_path = safe_output_path(root, "export_errors.json")
        error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        files["export_errors"] = error_path.name
        status_path = safe_output_path(root, "export_status.json")
        status_path.write_text(
            json.dumps(
                {
                    "status": status,
                    "requested_formats": list(selected),
                    "successful_formats": [item for item in selected if item in files],
                    "failed_formats": [item["format"] for item in errors],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        files["export_status"] = status_path.name
        return ReportExportResult(status=status, files=files, errors=tuple(errors))
