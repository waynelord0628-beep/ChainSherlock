import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from crypto_investigator.reports.errors import PdfExportError
from crypto_investigator.reports.models import ReportDocument


class PdfReportExporter:
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
            styles = getSampleStyleSheet()
            for name in ("Title", "Heading1", "Heading2", "BodyText"):
                styles[name].fontName = font_name
            story = [
                Paragraph(document.title, styles["Title"]),
                Paragraph(f"報告編號：{document.metadata.report_id}", styles["BodyText"]),
                Spacer(1, 5 * mm),
            ]
            for section in document.sections:
                story.append(Paragraph(section.title, styles["Heading1"]))
                for block in section.content_blocks:
                    story.append(Paragraph(block, styles["BodyText"]))
                for table in section.tables:
                    data = [list(table.columns), *[list(row) for row in table.rows]]
                    if data and data[0]:
                        rendered = Table(data, repeatRows=1)
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
            SimpleDocTemplate(str(path), pagesize=A4).build(story)
            return path
        except PdfExportError:
            raise
        except Exception as error:
            raise PdfExportError("Unable to export PDF report") from error
