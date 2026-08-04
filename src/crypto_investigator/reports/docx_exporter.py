from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Mm, Pt

from crypto_investigator.reports.errors import DocxExportError
from crypto_investigator.reports.models import ReportDocument


class DocxReportExporter:
    @staticmethod
    def _set_run_font(run, *, address: bool = False) -> None:
        run.font.name = "Consolas" if address else "Times New Roman"
        run._element.get_or_add_rPr().rFonts.set(
            qn("w:eastAsia"), "標楷體"
        )
        run._element.get_or_add_rPr().rFonts.set(
            qn("w:ascii"), "Consolas" if address else "Times New Roman"
        )
        run._element.get_or_add_rPr().rFonts.set(
            qn("w:hAnsi"), "Consolas" if address else "Times New Roman"
        )

    @staticmethod
    def _add_page_number(paragraph) -> None:
        run = paragraph.add_run("第 ")
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        run._r.addnext(field)
        paragraph.add_run(" 頁")

    def write(self, document: ReportDocument, path: Path) -> Path:
        try:
            output = Document()
            section = output.sections[0]
            has_wide_tables = any(
                len(table.columns) > 5
                for item in document.sections
                for table in item.tables
            )
            section.page_width = Mm(297 if has_wide_tables else 210)
            section.page_height = Mm(210 if has_wide_tables else 297)
            section.top_margin = section.bottom_margin = Mm(20)
            section.left_margin = section.right_margin = Mm(22)
            for style_name in ("Normal", "Title", "Heading 1", "Heading 2"):
                style = output.styles[style_name]
                style.font.name = "Times New Roman"
                style._element.get_or_add_rPr().rFonts.set(
                    qn("w:eastAsia"), "標楷體"
                )
                style._element.get_or_add_rPr().rFonts.set(
                    qn("w:ascii"), "Times New Roman"
                )
                style._element.get_or_add_rPr().rFonts.set(
                    qn("w:hAnsi"), "Times New Roman"
                )
            output.styles["Normal"].font.size = Pt(10.5)
            section.header.paragraphs[0].text = "ChainSherlock"
            self._add_page_number(section.footer.paragraphs[0])
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
                    columns = table_data.columns
                    rows = table_data.rows
                    table = output.add_table(
                        rows=1, cols=max(1, len(columns))
                    )
                    table.style = "Table Grid"
                    for index, column in enumerate(columns):
                        table.rows[0].cells[index].text = column
                        for run in table.rows[0].cells[index].paragraphs[0].runs:
                            self._set_run_font(run, address=True)
                    for row in rows:
                        cells = table.add_row().cells
                        for index, value in enumerate(row):
                            cells[index].text = value
                            for run in cells[index].paragraphs[0].runs:
                                self._set_run_font(run, address=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            output.save(path)
            return path
        except Exception as error:
            raise DocxExportError("Unable to export DOCX report") from error
