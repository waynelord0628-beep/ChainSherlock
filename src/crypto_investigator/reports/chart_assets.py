from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from crypto_investigator.reports.formatting import abbreviate_identifier
from crypto_investigator.reports.models import ReportDocument, ReportFigure


NAVY = "#17233B"
TEAL = "#16857A"
BLUE = "#3973B9"
PALE = "#E8EEF5"
GRID = "#CBD5E1"
TEXT = "#172033"
MUTED = "#64748B"


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _font(size: int, *, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _label(address: str) -> str:
    return abbreviate_identifier(address, head=8, tail=7)


def _money(value) -> str:
    return f"{_decimal(value):,.2f}"


def _canvas(size):
    image = Image.new("RGB", size, "white")
    return image, ImageDraw.Draw(image)


def _arrow(draw, start, end, color) -> None:
    draw.line((start, end), fill=color, width=4)
    x, y = end
    draw.polygon(((x, y), (x - 14, y - 8), (x - 14, y + 8)), fill=color)


def _flow_chart(product: dict) -> Image.Image:
    principal = product.get("principal_asset") or {}
    sources = tuple(principal.get("sources") or ())[:5]
    destinations = tuple(principal.get("destinations") or ())[:5]
    image, draw = _canvas((1400, 720))
    draw.text((55, 35), "Top 5 Sources", font=_font(28, bold=True), fill=NAVY)
    draw.text((1030, 35), "Top 5 Destinations", font=_font(28, bold=True), fill=NAVY)
    draw.rounded_rectangle((580, 285, 820, 420), radius=18, fill=NAVY)
    draw.text((700, 320), "TARGET", anchor="mm", font=_font(26, bold=True), fill="white")
    draw.text((700, 375), "USDT", anchor="mm", font=_font(22), fill="white")
    for index in range(5):
        y = 130 + index * 105
        if index < len(sources):
            item = sources[index]
            draw.rounded_rectangle((45, y, 420, y + 76), radius=10, fill=PALE, outline=GRID, width=2)
            draw.text((65, y + 14), f"{index + 1}. {_label(str(item.get('address') or ''))}", font=_font(18, bold=True), fill=TEXT)
            draw.text((65, y + 44), f"{_money(item.get('amount'))} USDT", font=_font(17), fill=TEXT)
            _arrow(draw, (425, y + 38), (570, 352), TEAL)
        if index < len(destinations):
            item = destinations[index]
            draw.rounded_rectangle((980, y, 1355, y + 76), radius=10, fill=PALE, outline=GRID, width=2)
            draw.text((1000, y + 14), f"{index + 1}. {_label(str(item.get('address') or ''))}", font=_font(18, bold=True), fill=TEXT)
            draw.text((1000, y + 44), f"{_money(item.get('amount'))} USDT", font=_font(17), fill=TEXT)
            _arrow(draw, (830, 352), (970, y + 38), BLUE)
    draw.text(
        (700, 690),
        "Independent rankings - not transaction-level path tracing",
        anchor="mm",
        font=_font(16),
        fill=MUTED,
    )
    return image


def _monthly_chart(product: dict) -> Image.Image:
    principal = product.get("principal_asset") or {}
    rows = tuple(principal.get("monthly") or ())
    image, draw = _canvas((1500, 760))
    draw.text((60, 35), "Monthly USDT Inflow / Outflow", font=_font(30, bold=True), fill=NAVY)
    values = [
        max(_decimal(item.get("incoming")), _decimal(item.get("outgoing")))
        for item in rows
    ]
    maximum = max(values, default=Decimal("1")) or Decimal("1")
    left, top, bottom, right = 90, 110, 630, 1435
    draw.line((left, top, left, bottom), fill=GRID, width=2)
    draw.line((left, bottom, right, bottom), fill=GRID, width=2)
    group = (right - left) / max(len(rows), 1)
    bar_width = max(7, int(group * 0.3))
    for index, item in enumerate(rows):
        x = int(left + index * group + group * 0.15)
        incoming = _decimal(item.get("incoming"))
        outgoing = _decimal(item.get("outgoing"))
        in_height = int(float(incoming / maximum) * (bottom - top))
        out_height = int(float(outgoing / maximum) * (bottom - top))
        draw.rectangle((x, bottom - in_height, x + bar_width, bottom), fill=TEAL)
        draw.rectangle((x + bar_width + 3, bottom - out_height, x + 2 * bar_width + 3, bottom), fill=BLUE)
        period = str(item.get("period") or "")
        draw.text((x - 4, bottom + 12), period[-5:], font=_font(12), fill=TEXT)
    draw.rectangle((1110, 46, 1135, 62), fill=TEAL)
    draw.text((1145, 43), "Inflow", font=_font(17), fill=TEXT)
    draw.rectangle((1240, 46, 1265, 62), fill=BLUE)
    draw.text((1275, 43), "Outflow", font=_font(17), fill=TEXT)
    draw.text((90, 710), f"Peak monthly value: {_money(maximum)} USDT", font=_font(16), fill=MUTED)
    return image


def _destination_chart(product: dict) -> Image.Image:
    principal = product.get("principal_asset") or {}
    rows = tuple(principal.get("destinations") or ())[:5]
    image, draw = _canvas((1400, 620))
    draw.text((55, 35), "Top 5 First-Hop Destinations", font=_font(30, bold=True), fill=NAVY)
    maximum = max((_decimal(item.get("amount")) for item in rows), default=Decimal("1")) or Decimal("1")
    for index, item in enumerate(rows):
        y = 125 + index * 92
        amount = _decimal(item.get("amount"))
        width = int(float(amount / maximum) * 720)
        draw.text((55, y), f"{index + 1}. {_label(str(item.get('address') or ''))}", font=_font(18, bold=True), fill=TEXT)
        draw.rounded_rectangle((365, y, 365 + width, y + 38), radius=6, fill=BLUE)
        draw.text((1110, y + 7), _money(amount), font=_font(17), fill=TEXT)
        draw.text((1340, y + 7), f"{_decimal(item.get('share')) * 100:.2f}%", anchor="ra", font=_font(17), fill=TEXT)
    draw.text((365, 575), "USDT amount", font=_font(16), fill=MUTED)
    return image


def attach_deterministic_chart_assets(
    document: ReportDocument,
    output_directory: Path,
) -> ReportDocument:
    product = dict(document.metadata.first_hop_product or {})
    if not product:
        return document
    chart_directory = output_directory / "charts"
    chart_directory.mkdir(parents=True, exist_ok=True)
    specifications = {
        "deterministic_flow_chart": (
            "first_hop_flow.png",
            _flow_chart(product),
            "USDT 前五大來源、調查標的與前五大去向。",
        ),
        "deterministic_monthly_chart": (
            "monthly_usdt_flow.png",
            _monthly_chart(product),
            "USDT 每月流入與流出金額。",
        ),
        "deterministic_destination_chart": (
            "top_destinations.png",
            _destination_chart(product),
            "USDT 前五大第一層去向金額與占比。",
        ),
    }
    figures = {}
    for section_id, (filename, image, description) in specifications.items():
        target = chart_directory / filename
        image.save(target, format="PNG", optimize=True)
        figures[section_id] = ReportFigure(
            figure_id=section_id,
            title=description,
            path=f"charts/{filename}",
            description=description,
        )
    return replace(
        document,
        sections=tuple(
            replace(section, figures=(figures[section.section_id],), tables=())
            if section.section_id in figures
            else section
            for section in document.sections
        ),
    )
