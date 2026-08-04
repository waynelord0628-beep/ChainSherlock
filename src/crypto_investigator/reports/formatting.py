import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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
    return text


def format_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return redact(value)


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
