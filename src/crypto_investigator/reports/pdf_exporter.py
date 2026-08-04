import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String

from crypto_investigator.reports.errors import PdfExportError
from crypto_investigator.reports.formatting import abbreviate_identifier
from crypto_investigator.reports.models import ReportDocument


_WINDOWS_CJK_FONTS = (
    ("kaiu.ttf", "標楷體"),
    ("msjh.ttc", "Microsoft JhengHei"),
)


def resolve_cjk_font(
    font_path: Path | None = None,
) -> tuple[Path | None, str, str | None]:
    if font_path is not None:
        return font_path, "explicit", font_path.stem
    if value := os.getenv("CHAINSHERLOCK_PDF_CJK_FONT"):
        path = Path(value)
        return path, "environment", path.stem
    windows = os.getenv("WINDIR")
    if windows:
        fonts = Path(windows) / "Fonts"
        for filename, name in _WINDOWS_CJK_FONTS:
            candidate = fonts / filename
            if candidate.is_file():
                return candidate, "system", name
    return None, "unavailable", None


def pdf_font_status() -> dict[str, str | bool | None]:
    path, source, name = resolve_cjk_font()
    return {
        "available": bool(path and path.is_file()),
        "font_name": name,
        "source": source,
    }


class PdfReportExporter:
    @staticmethod
    def _pdf_cell(value: str, column: str) -> str:
        key = column.casefold()
        if column != "完整地址" and any(
            marker in key for marker in ("address", "地址", "tx hash", "tx_hash")
        ):
            return abbreviate_identifier(str(value))
        return str(value)

    @staticmethod
    def _column_widths(columns, available_width):
        weights = []
        for column in columns:
            key = column.casefold()
            if column in {"Evidence ID"}:
                weight = 0.85
            elif column in {"檔名"}:
                weight = 2.5
            elif column in {"類型"}:
                weight = 1.1
            elif column in {"SHA-256"}:
                weight = 1.5
            elif column in {"備註"}:
                weight = 1.6
            elif column in {"Address ID", "地址編號"}:
                weight = 1.05
            elif column == "完整地址":
                weight = 3.2
            elif column in {"排名", "信心", "方向", "資產", "完整度", "截斷"}:
                weight = 0.7
            elif any(item in key for item in ("時間", "首次", "最後", "開始", "結束")):
                weight = 1.65
            elif any(item in column for item in ("金額", "流入", "流出")):
                weight = 1.4
            elif any(item in key for item in ("地址", "來源", "去向", "sha-256")):
                weight = 1.8
            elif any(item in key for item in ("限制", "原因", "警告", "備註", "觀察", "事實")):
                weight = 2.1
            else:
                weight = 1.0
            weights.append(weight)
        total = sum(weights) or 1
        return tuple(available_width * mm * item / total for item in weights)

    def _page_number(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(self._latin_font_name, 9)
        canvas.drawString(18 * mm, 12 * mm, self._report_id)
        canvas.drawCentredString(A4[0] / 2, 12 * mm, f"{doc.page}")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, "UTC+8")
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
        configured, _, _ = resolve_cjk_font(font_path)
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
            self._report_id = document.metadata.report_id
            styles = getSampleStyleSheet()
            for name in ("Title", "Heading1", "Heading2", "BodyText"):
                styles[name].fontName = font_name
            styles["BodyText"].fontSize = 8
            styles["BodyText"].leading = 10
            styles["BodyText"].splitLongWords = False
            styles["Heading1"].keepWithNext = True
            styles["Heading2"].keepWithNext = True
            styles["BodyText"].allowWidows = False
            styles["BodyText"].allowOrphans = False
            story = []
            for section in document.sections:
                if section.section_id == "cover":
                    story.append(Spacer(1, 24 * mm))
                    cover_header = Drawing(430, 34)
                    navy = colors.HexColor("#16213E")
                    teal = colors.HexColor("#138A84")
                    cover_header.add(Rect(0, 29, 430, 3, fillColor=navy, strokeColor=None))
                    cover_header.add(Rect(0, 24, 116, 3, fillColor=teal, strokeColor=None))
                    cover_header.add(
                        String(
                            0,
                            5,
                            "FORENSIC ANALYSIS DOSSIER",
                            fontName=self._latin_font_name,
                            fontSize=8,
                            fillColor=colors.HexColor("#64748B"),
                        )
                    )
                    story.append(cover_header)
                    story.append(Spacer(1, 13 * mm))
                    story.append(
                        Paragraph(
                            self._styled_text(
                                "ChainSherlock 調查分析報告",
                                self._latin_font_name,
                            ),
                            styles["Title"],
                        )
                    )
                    story.append(
                        Paragraph(
                            self._styled_text(
                                "Blockchain Fund Flow Investigation Report",
                                self._latin_font_name,
                            ),
                            styles["Heading2"],
                        )
                    )
                    cover_mark = Drawing(170, 118)
                    pale = colors.HexColor("#E7EBF0")
                    cover_mark.add(
                        Circle(
                            85,
                            59,
                            43,
                            strokeColor=pale,
                            strokeWidth=2.5,
                            fillColor=colors.HexColor("#FAFBFC"),
                        )
                    )
                    cover_mark.add(
                        String(
                            67,
                            30,
                            "B",
                            fontName=self._latin_font_name,
                            fontSize=70,
                            fillColor=pale,
                        )
                    )
                    cover_mark.add(Line(69, 21, 69, 97, strokeColor=pale, strokeWidth=3))
                    cover_mark.add(Line(79, 19, 79, 99, strokeColor=pale, strokeWidth=3))
                    story.append(cover_mark)
                    story.append(Spacer(1, 8 * mm))
                    cover_metadata = []
                    for block in section.content_blocks:
                        cover_metadata.append(
                            Paragraph(
                                self._styled_text(block, self._latin_font_name),
                                styles["BodyText"],
                            )
                        )
                        cover_metadata.append(Spacer(1, 2 * mm))
                    metadata_card = Table(
                        [[cover_metadata]],
                        colWidths=[136 * mm],
                        hAlign="CENTER",
                    )
                    metadata_card.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F8FA")),
                                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#D9DEE7")),
                                ("LINEBEFORE", (0, 0), (0, -1), 3, teal),
                                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (-1, -1), 12),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                            ]
                        )
                    )
                    story.append(metadata_card)
                    story.append(PageBreak())
                    continue
                if section.section_id == "table_of_contents":
                    pale = colors.HexColor("#D9DEE7")
                    toc_title = styles["Title"].clone("BookletContentsTitle")
                    toc_title.alignment = 1
                    story.append(Spacer(1, 10 * mm))
                    story.append(Paragraph("目錄", toc_title))
                    toc_subtitle = styles["Heading2"].clone(
                        "BookletContentsSubtitle"
                    )
                    toc_subtitle.alignment = 1
                    story.append(
                        Paragraph(
                            f'<font name="{self._latin_font_name}">CONTENTS</font>',
                            toc_subtitle,
                        )
                    )
                    story.append(Spacer(1, 12 * mm))
                    midpoint = (len(section.content_blocks) + 1) // 2
                    left = section.content_blocks[:midpoint]
                    right = section.content_blocks[midpoint:]
                    rows = [
                        (
                            left[index] if index < len(left) else "",
                            right[index] if index < len(right) else "",
                        )
                        for index in range(max(len(left), len(right)))
                    ]
                    toc_style = styles["BodyText"].clone("BookletContentsItem")
                    toc_style.fontSize = 10
                    toc_style.leading = 16
                    toc = Table(
                        [
                            [
                                Paragraph(
                                    self._styled_text(value, self._latin_font_name),
                                    toc_style,
                                )
                                for value in row
                            ]
                            for row in rows
                        ],
                        colWidths=(80 * mm, 80 * mm),
                    )
                    toc.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                ("LINEABOVE", (0, 0), (-1, 0), 0.5, pale),
                            ]
                        )
                    )
                    story.append(toc)
                    story.append(PageBreak())
                    continue
                if section.section_id.startswith("asset_analysis_"):
                    story.append(PageBreak())
                story.append(
                    Paragraph(
                        self._styled_text(section.title, self._latin_font_name),
                        styles["Heading1"],
                    )
                )
                for block_index, block in enumerate(section.content_blocks):
                    block_style = styles["BodyText"]
                    if (
                        section.tables
                        and block_index == len(section.content_blocks) - 1
                    ):
                        block_style = styles["BodyText"].clone(
                            f"Lead-{section.section_id}"
                        )
                        block_style.keepWithNext = True
                    story.append(
                        Paragraph(
                            self._styled_text(block, self._latin_font_name),
                            block_style,
                        )
                    )
                for table in section.tables:
                    story.append(
                        Paragraph(
                            self._styled_text(table.title, self._latin_font_name),
                            styles["Heading2"],
                        )
                    )
                    table_cell_style = styles["BodyText"].clone(
                        f"TableCell-{section.section_id}-{table.table_id}"
                    )
                    table_cell_style.fontSize = (
                        8 if section.section_id == "appendix" else 8.5
                    )
                    table_cell_style.leading = (
                        9.5 if section.section_id == "appendix" else 10
                    )
                    data = [
                        list(table.columns),
                        *[
                            [
                                self._pdf_cell(value, table.columns[index])
                                for index, value in enumerate(row)
                            ]
                            for row in table.rows
                        ],
                    ]
                    available_width = 252 if len(table.columns) > 8 else 165
                    widths = self._column_widths(
                        table.columns, available_width
                    )
                    data = [
                        [
                            Paragraph(
                                self._styled_text(str(value), self._table_font_name),
                                table_cell_style,
                            )
                            for value in row
                        ]
                        for row in data
                    ]
                    if data and data[0]:
                        rendered = Table(
                            data,
                            repeatRows=1,
                            colWidths=widths,
                            splitByRow=1,
                            splitInRow=0,
                        )
                        commands = [
                                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                    (
                                        "FONTSIZE",
                                        (0, 0),
                                        (-1, -1),
                                        table_cell_style.fontSize,
                                    ),
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                        for index, column in enumerate(table.columns):
                            if any(
                                marker in column
                                for marker in (
                                    "金額", "筆數", "交易數", "比例", "占比",
                                    "事件數", "取得筆數",
                                )
                            ):
                                commands.append(
                                    ("ALIGN", (index, 1), (index, -1), "RIGHT")
                                )
                        rendered.setStyle(TableStyle(commands))
                        story.append(rendered)
                story.append(Spacer(1, 3 * mm))
                if section.section_id == "table_of_contents":
                    story.append(PageBreak())
            path.parent.mkdir(parents=True, exist_ok=True)
            SimpleDocTemplate(
                str(path),
                pagesize=(
                    landscape(A4)
                    if any(
                        len(table.columns) > 8
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
