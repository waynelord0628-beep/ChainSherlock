from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from crypto_investigator.investigation.investigation_result import LabelRecord


ALLOWED_CATEGORIES = {
    "exchange", "vasp", "otc", "payment", "bridge", "dex", "mixer", "service",
    "victim", "suspect", "law_enforcement", "sanctioned", "unknown",
}


def normalize_label_address(chain: str, address: str) -> str:
    value = address.strip()
    return value.casefold() if chain.casefold() == "ethereum" else value


class LabelRegistry:
    def __init__(self, records=()):
        self.records = tuple(records)

    @classmethod
    def import_file(cls, path: Path):
        suffix = path.suffix.casefold()
        if suffix == ".csv":
            frame = pd.read_csv(path, dtype=str).fillna("")
            rows = frame.to_dict(orient="records")
        elif suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(path, dtype=str).fillna("")
            rows = frame.to_dict(orient="records")
        elif suffix == ".json":
            rows = json.loads(path.read_text(encoding="utf-8"))
        else:
            raise ValueError("Supported label formats are CSV, XLS, XLSX, and JSON")
        records = {}
        verification_priority = {
            "manual_confirmed": 5,
            "trusted_local": 4,
            "provider_label": 3,
            "unverified_candidate": 2,
            "unlabeled": 1,
        }
        for row in rows:
            chain = str(row.get("chain", "unknown")).strip().casefold()
            address = normalize_label_address(chain, str(row.get("address", "")))
            if not address:
                continue
            category = str(row.get("category", "unknown")).strip().casefold()
            if category not in ALLOWED_CATEGORIES:
                category = "unknown"
            key = (chain, address)
            candidate = LabelRecord(
                address=address,
                label=str(row.get("label", "")).strip(),
                category=category,
                source=str(row.get("source", path.name)).strip() or path.name,
                chain=chain,
                confidence=str(row.get("confidence", "medium")).strip().casefold(),
                notes=str(row.get("notes", "")).strip(),
                first_seen=cls._datetime(row.get("first_seen")),
                last_verified=cls._datetime(row.get("last_verified")),
                reference=(
                    str(row.get("reference")).strip()
                    if row.get("reference") is not None
                    and str(row.get("reference")).strip()
                    else None
                ),
                verification_status=(
                    str(row.get("verification_status", "unverified_candidate"))
                    .strip()
                    .casefold()
                ),
                imported_at=cls._datetime(row.get("imported_at")),
            )
            current = records.get(key)
            if current is None or verification_priority.get(
                candidate.verification_status, 0
            ) > verification_priority.get(current.verification_status, 0):
                records[key] = candidate
        return cls(records[key] for key in sorted(records))

    def check(self, chain: str, address: str):
        normalized = normalize_label_address(chain, address)
        return tuple(
            item for item in self.records
            if item.chain == chain.casefold() and item.address == normalized
        )

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [
                    {
                        "chain": item.chain,
                        "address": item.address,
                        "label": item.label,
                        "category": item.category,
                        "source": item.source,
                        "confidence": item.confidence,
                        "notes": item.notes,
                        "first_seen": item.first_seen.isoformat() if item.first_seen else None,
                        "last_verified": item.last_verified.isoformat() if item.last_verified else None,
                        "reference": item.reference,
                        "verification_status": item.verification_status,
                        "imported_at": (
                            item.imported_at.isoformat() if item.imported_at else None
                        ),
                    }
                    for item in self.records
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _datetime(value):
        if value is None or str(value).strip() == "":
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
