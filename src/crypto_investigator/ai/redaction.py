import hashlib
import re


SECRET = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|secret|token)\s*[:=]\s*\S+"
)
TOKEN = re.compile(r"(?i)\bsk-[a-z0-9_-]{20,}\b")
ABSOLUTE = re.compile(r"(?i)(?:[a-z]:\\|/(?:home|users|var|etc)/)\S+")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def redact_text(value: object, limit: int = 1000) -> str:
    text = CONTROL.sub("", str(value))
    text = SECRET.sub(r"\1=[REDACTED]", text)
    text = TOKEN.sub("[REDACTED_SECRET]", text)
    text = ABSOLUTE.sub("[REDACTED_PATH]", text)
    return text[:limit]


def private_identifier(value: str) -> str:
    return f"addr_{hashlib.sha256(value.encode()).hexdigest()[:16]}"
