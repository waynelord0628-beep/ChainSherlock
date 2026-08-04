from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Mm, Pt

from crypto_investigator.reports.errors import DocxExportError
from crypto_investigator.reports.models import ReportDocument


class DocxReportExporter:
    @staticmethod
    def _repeat_table_header(row) -> None:
        properties = row._tr.get_or_add_trPr()
        header = OxmlElement("w:tblHeader")
        header.set(qn("w:val"), "true")
        properties.append(header)

    @staticmethod
    def _prevent_row_split(row) -> None:
        properties = row._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        properties.append(cant_split)

    @staticmethod
    def _column_weights(columns):
        values = []
        for column in columns:
            if column in {"排名", "信心", "方向", "資產", "完整度", "截斷"}:
                values.append(0.7)
            elif any(item in column for item in ("時間", "首次", "最後", "開始", "結束")):
                values.append(1.6)
            elif any(item in column.casefold() for item in ("地址", "來源", "去向", "sha-256")):
                values.append(1.8)
            elif any(item in column for item in ("限制", "原因", "警告", "備註", "觀察", "事實")):
                values.append(2.1)
            else:
                values.append(1.0)
        return values
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
            section.page_width = Mm(210)
            section.page_height = Mm(297)
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
            for style_name in ("Title", "Heading 1", "Heading 2"):
                output.styles[style_name].paragraph_format.keep_with_next = True
            output.styles["Normal"].paragraph_format.widow_control = True
            section.header.paragraphs[0].text = (
                f"ChainSherlock | {document.metadata.report_id} | UTC+8"
            )
            footer = section.footer.paragraphs[0]
            footer.add_run(f"{document.metadata.report_id} | ")
            self._add_page_number(footer)
            footer.add_run(" | UTC+8")
            for report_section in document.sections:
                if report_section.section_id == "cover":
                    output.add_paragraph()
                    output.add_paragraph()
                    title = output.add_paragraph()
                    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = title.add_run("ChainSherlock 調查分析報告")
                    run.bold = True
                    run.font.size = Pt(26)
                    self._set_run_font(run)
                    subtitle = output.add_paragraph()
                    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = subtitle.add_run(
                        "Blockchain Fund Flow Investigation Report"
                    )
                    run.font.size = Pt(15)
                    self._set_run_font(run)
                    output.add_paragraph()
                    for block in report_section.content_blocks:
                        paragraph = output.add_paragraph(block)
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    output.add_page_break()
                    continue
                if report_section.section_id.startswith("asset_analysis_"):
                    output.add_page_break()
                heading = output.add_heading(report_section.title, level=1)
                heading.paragraph_format.keep_with_next = True
                for block in report_section.content_blocks:
                    paragraph = output.add_paragraph(block)
                    paragraph.paragraph_format.widow_control = True
                    if report_section.section_id.startswith("ai_"):
                        paragraph.paragraph_format.keep_together = True
                for table_data in report_section.tables:
                    wide = len(table_data.columns) > 8
                    if wide:
                        current = output.add_section(WD_SECTION.NEW_PAGE)
                        current.page_width = Mm(297)
                        current.page_height = Mm(210)
                        current.top_margin = current.bottom_margin = Mm(20)
                        current.left_margin = current.right_margin = Mm(22)
                    table_heading = output.add_heading(table_data.title, level=2)
                    table_heading.paragraph_format.keep_with_next = True
                    columns = table_data.columns
                    rows = table_data.rows
                    table = output.add_table(
                        rows=1, cols=max(1, len(columns))
                    )
                    table.style = "Table Grid"
                    table.autofit = False
                    table.alignment = WD_TABLE_ALIGNMENT.CENTER
                    weights = self._column_weights(columns)
                    usable_mm = 253 if wide else 166
                    total_weight = sum(weights) or 1
                    for index, column in enumerate(columns):
                        width = Mm(usable_mm * weights[index] / total_weight)
                        table.columns[index].width = width
                        table.rows[0].cells[index].text = column
                        table.rows[0].cells[index].width = width
                        table.rows[0].cells[index].vertical_alignment = (
                            WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        )
                        for run in table.rows[0].cells[index].paragraphs[0].runs:
                            self._set_run_font(run, address=True)
                    self._repeat_table_header(table.rows[0])
                    for row in rows:
                        cells = table.add_row().cells
                        self._prevent_row_split(table.rows[-1])
                        for index, value in enumerate(row):
                            cells[index].text = value
                            cells[index].width = Mm(
                                usable_mm * weights[index] / total_weight
                            )
                            cells[index].vertical_alignment = (
                                WD_CELL_VERTICAL_ALIGNMENT.CENTER
                            )
                            if any(
                                marker in columns[index]
                                for marker in (
                                    "金額", "筆數", "交易數", "比例",
                                    "占比", "事件數", "取得筆數",
                                )
                            ):
                                cells[index].paragraphs[0].alignment = (
                                    WD_ALIGN_PARAGRAPH.RIGHT
                                )
                            for run in cells[index].paragraphs[0].runs:
                                self._set_run_font(run, address=True)
                    if wide:
                        current = output.add_section(WD_SECTION.NEW_PAGE)
                        current.page_width = Mm(210)
                        current.page_height = Mm(297)
                        current.top_margin = current.bottom_margin = Mm(20)
                        current.left_margin = current.right_margin = Mm(22)
                if report_section.section_id == "table_of_contents":
                    output.add_page_break()
            path.parent.mkdir(parents=True, exist_ok=True)
            output.save(path)
            return path
        except Exception as error:
            raise DocxExportError("Unable to export DOCX report") from error
