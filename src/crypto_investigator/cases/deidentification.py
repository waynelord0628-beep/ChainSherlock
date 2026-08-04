from __future__ import annotations

import hashlib
import re
from secrets import token_bytes
from typing import Any

_ADDRESS = re.compile(
    r"(?:0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33}|bc1[ac-hj-np-z02-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})"
)
_TX = re.compile(r"(?:0x[a-fA-F0-9]{64}|(?<![a-fA-F0-9])[a-fA-F0-9]{64}(?![a-fA-F0-9]))")
_REMOVE_KEYS = {
    "case_number",
    "confirmed_by",
    "reviewed_by",
    "review_notes",
    "resolution_notes",
    "notes",
    "title",
}


class Deidentifier:
    def __init__(self) -> None:
        self._salt = token_bytes(32)
        self._aliases: dict[tuple[str, str], str] = {}
        self.counts = {"address": 0, "transaction": 0, "removed_fields": 0}

    def alias(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self._aliases:
            digest = hashlib.sha256(self._salt + value.encode()).hexdigest()[:12]
            self._aliases[key] = f"{kind}_{digest}"
            self.counts[kind] += 1
        return self._aliases[key]

    def transform(self, value: Any, *, key: str = "") -> Any:
        if key.lower() in _REMOVE_KEYS:
            self.counts["removed_fields"] += 1
            return None
        if isinstance(value, dict):
            return {
                str(item_key): self.transform(item, key=str(item_key))
                for item_key, item in value.items()
                if str(item_key).lower() not in _REMOVE_KEYS
            }
        if isinstance(value, list):
            return [self.transform(item) for item in value]
        if isinstance(value, str):
            transformed = _TX.sub(
                lambda match: self.alias("transaction", match.group(0)), value
            )
            return _ADDRESS.sub(
                lambda match: self.alias("address", match.group(0)), transformed
            )
        return value

    def manifest(self) -> dict[str, Any]:
        return {
            "method": "salted_sha256_pseudonyms",
            "mapping_included": False,
            "salt_included": False,
            "counts": dict(self.counts),
            "limitations": [
                "Pseudonymization reduces direct identifiers but is not a guarantee of anonymity.",
                "Raw evidence and execution artifacts are excluded.",
            ],
        }
