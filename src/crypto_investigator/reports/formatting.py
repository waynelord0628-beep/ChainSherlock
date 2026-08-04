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
