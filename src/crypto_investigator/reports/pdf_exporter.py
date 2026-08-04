import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from crypto_investigator.reports.errors import PdfExportError
from crypto_investigator.reports.models import ReportDocument


class PdfReportExporter:
    def _page_number(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(self._latin_font_name, 9)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, f"{doc.page}")
        canvas.restoreState()

    @staticmethod
    def _register_optional_windows_font(filename: str, name: str, fallback: str) -> str:
        windows = os.getenv("WINDIR")
        candidate = Path(windows) / "Fonts" / filename if windows else None
        if candidate and candidate.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(candidate)))
                return name
            except Exception:
                pass
        return fallback

    @staticmethod
    def _styled_text(value: str, latin_font: str) -> str:
        parts = []
        for segment in re.findall(r"[\x00-\x7f]+|[^\x00-\x7f]+", str(value)):
            escaped = escape(segment)
            if segment.isascii():
                parts.append(f'<font name="{latin_font}">{escaped}</font>')
            else:
                parts.append(escaped)
        return "".join(parts)

    def write(
        self, document: ReportDocument, path: Path, font_path: Path | None = None
    ) -> Path:
        configured = font_path or (
            Path(value)
            if (value := os.getenv("CHAINSHERLOCK_PDF_CJK_FONT"))
            else None
        )
        if configured is None or not configured.exists():
            raise PdfExportError(
                "A CJK font is required; configure CHAINSHERLOCK_PDF_CJK_FONT"
            )
        try:
            font_name = "ChainSherlockCJK"
            pdfmetrics.registerFont(TTFont(font_name, str(configured)))
            self._latin_font_name = self._register_optional_windows_font(
                "times.ttf", "ChainSherlockTimes", "Times-Roman"
            )
            self._table_font_name = self._register_optional_windows_font(
                "consola.ttf", "ChainSherlockConsolas", "Courier"
            )
            styles = getSampleStyleSheet()
            for name in ("Title", "Heading1", "Heading2", "BodyText"):
                styles[name].fontName = font_name
            story = [
                Paragraph(
                    self._styled_text(document.title, self._latin_font_name),
                    styles["Title"],
                ),
                Paragraph(
                    self._styled_text(
                        f"報告編號：{document.metadata.report_id}",
                        self._latin_font_name,
                    ),
                    styles["BodyText"],
                ),
                Spacer(1, 5 * mm),
            ]
            for section in document.sections:
                story.append(
                    Paragraph(
                        self._styled_text(section.title, self._latin_font_name),
                        styles["Heading1"],
                    )
                )
                for block in section.content_blocks:
                    story.append(
                        Paragraph(
                            self._styled_text(block, self._latin_font_name),
                            styles["BodyText"],
                        )
                    )
                for table in section.tables:
                    data = [list(table.columns), *[list(row) for row in table.rows]]
                    available_width = 252 if len(table.columns) > 5 else 165
                    widths = tuple(
                        available_width * mm / len(table.columns)
                        for _ in table.columns
                    )
                    data = [
                        [
                            Paragraph(
                                self._styled_text(str(value), self._table_font_name),
                                styles["BodyText"],
                            )
                            for value in row
                        ]
                        for row in data
                    ]
                    if data and data[0]:
                        rendered = Table(data, repeatRows=1, colWidths=widths)
                        rendered.setStyle(
                            TableStyle(
                                [
                                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                                ]
                            )
                        )
                        story.append(rendered)
                story.append(Spacer(1, 3 * mm))
            path.parent.mkdir(parents=True, exist_ok=True)
            SimpleDocTemplate(
                str(path),
                pagesize=(
                    landscape(A4)
                    if any(
                        len(table.columns) > 5
                        for item in document.sections
                        for table in item.tables
                    )
                    else A4
                ),
                bottomMargin=20 * mm,
            ).build(
                story,
                onFirstPage=self._page_number,
                onLaterPages=self._page_number,
            )
            return path
        except PdfExportError:
            raise
        except Exception as error:
            raise PdfExportError("Unable to export PDF report") from error
