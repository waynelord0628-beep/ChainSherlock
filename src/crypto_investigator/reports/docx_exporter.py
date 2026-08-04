from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from crypto_investigator.reports.errors import DocxExportError
from crypto_investigator.reports.models import ReportDocument


class DocxReportExporter:
    def write(self, document: ReportDocument, path: Path) -> Path:
        try:
            output = Document()
            section = output.sections[0]
            section.page_width = Mm(210)
            section.page_height = Mm(297)
            section.top_margin = section.bottom_margin = Mm(20)
            section.left_margin = section.right_margin = Mm(22)
            normal = output.styles["Normal"]
            normal.font.name = "Microsoft JhengHei"
            normal.font.size = Pt(10.5)
            normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft JhengHei")
            output.add_heading(document.title, 0)
            output.add_paragraph(f"報告編號：{document.metadata.report_id}")
            output.add_paragraph(
                f"資料完整度：{document.metadata.analysis_completeness}"
            )
            for report_section in document.sections:
                output.add_heading(report_section.title, level=1)
                for block in report_section.content_blocks:
                    output.add_paragraph(block)
                for table_data in report_section.tables:
                    output.add_heading(table_data.title, level=2)
                    table = output.add_table(
                        rows=1, cols=max(1, len(table_data.columns))
                    )
                    table.style = "Table Grid"
                    for index, column in enumerate(table_data.columns):
                        table.rows[0].cells[index].text = column
                    for row in table_data.rows:
                        cells = table.add_row().cells
                        for index, value in enumerate(row):
                            cells[index].text = value
            path.parent.mkdir(parents=True, exist_ok=True)
            output.save(path)
            return path
        except Exception as error:
            raise DocxExportError("Unable to export DOCX report") from error
