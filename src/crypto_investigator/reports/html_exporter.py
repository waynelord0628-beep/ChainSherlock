from pathlib import Path

from crypto_investigator.reports.errors import HtmlExportError
from crypto_investigator.reports.models import ReportDocument
from crypto_investigator.reports.templates import template_environment


class HtmlReportExporter:
    def write(self, document: ReportDocument, path: Path) -> Path:
        try:
            content = template_environment(html=True).get_template(
                "report_zh_tw.html.j2"
            ).render(document=document)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return path
        except Exception as error:
            raise HtmlExportError("Unable to export HTML report") from error
