import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from crypto_investigator.reports.errors import ReportSecurityError

SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|token)(\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(apikey=)([^&\s]+)"),
)


def redact(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 3:
            text = pattern.sub(r"\1\2[REDACTED]", text)
        else:
            text = pattern.sub(r"\1[REDACTED]", text)
    text = re.sub(r"[A-Za-z]:\\[^\s]+|/(?:home|Users)/[^\s]+", "[PATH]", text)
    text = re.sub(r"(?:\.\.[\\/])+", "[PATH]/", text)
    text = re.sub(r"(?i)\bon[a-z]+\s*=", "[EVENT] ", text)
    text = re.sub(r"(?i)javascript\s*:", "[SCRIPT] ", text)
    if text.startswith(("=", "+", "-", "@")):
        text = "'" + text
    text = text.replace("<", "＜").replace(">", "＞")
    return text


def format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return "；".join(
            f"{redact(key)}：{format_value(item)}"
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        ) or "—"
    if isinstance(value, (tuple, list, set, frozenset)):
        return "、".join(format_value(item) for item in value) or "—"
    return redact(value)


def format_compact(value: Any, *, maximum_items: int = 8, maximum_chars: int = 240) -> str:
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda pair: str(pair[0]))
        visible = ordered[:maximum_items]
        rendered = "；".join(
            f"{redact(key)}：{format_compact(item, maximum_items=maximum_items)}"
            for key, item in visible
        )
        if len(ordered) > maximum_items:
            rendered += f"；…省略 {len(ordered) - maximum_items} 項"
    elif isinstance(value, (tuple, list, set, frozenset)):
        ordered = list(value)
        rendered = "、".join(
            format_compact(item, maximum_items=maximum_items)
            for item in ordered[:maximum_items]
        )
        if len(ordered) > maximum_items:
            rendered += f"、…省略 {len(ordered) - maximum_items} 項"
    else:
        rendered = format_value(value)
    if len(rendered) > maximum_chars:
        return rendered[: maximum_chars - 16] + "…（完整值見 JSON）"
    return rendered


def format_datetime(value: Any, timezone: str = "UTC") -> str:
    if value in (None, "", "—"):
        return "—"
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )
    if moment.tzinfo is None or moment.utcoffset() is None:
        return "unavailable（缺少時區）"
    return moment.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")


def format_percent(value: Any) -> str:
    return f"{Decimal(str(value)) * Decimal('100'):,.2f}%"


def format_amount(value: Any, *, maximum_decimals: int = 18) -> str:
    amount = Decimal(str(value))
    rendered = f"{amount:,.{maximum_decimals}f}".rstrip("0").rstrip(".")
    return rendered or "0"


def format_duration(value: Any) -> str:
    if value in (None, "", "—"):
        return "—"
    total_minutes = int(Decimal(str(value)) // Decimal("60"))
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days} 天")
    if hours:
        parts.append(f"{hours} 小時")
    if minutes or not parts:
        parts.append(f"{minutes} 分")
    return " ".join(parts)


def abbreviate_identifier(value: str, *, head: int = 8, tail: int = 6) -> str:
    safe = redact(value)
    if len(safe) <= head + tail + 1:
        return safe
    return f"{safe[:head]}…{safe[-tail:]}"


def safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    base = root.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError("Path is outside the allowed evidence root")
    return resolved.relative_to(base).as_posix()


def safe_output_path(output_directory: Path, filename: str) -> Path:
    root = output_directory.resolve()
    candidate = (root / filename).resolve()
    if candidate.parent != root or Path(filename).is_absolute():
        raise ReportSecurityError("Output path must remain inside the output directory")
    return candidate


def validate_output_directory(path: Path) -> Path:
    if ".." in path.parts:
        raise ReportSecurityError("Output directory cannot contain parent traversal")
    return path.resolve()
