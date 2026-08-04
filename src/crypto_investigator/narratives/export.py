from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from crypto_investigator.narratives import models
from crypto_investigator.narratives.models import NarrativeInput, NarrativeResult


def encode(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {"__type__": type(value).__name__, **{item.name: encode(getattr(value, item.name)) for item in fields(value)}}
    if isinstance(value, Enum):
        return {"__enum__": f"{type(value).__name__}:{value.value}"}
    if isinstance(value, tuple):
        return {"__tuple__": [encode(item) for item in value]}
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__datetime__" in value:
        return datetime.fromisoformat(value["__datetime__"])
    if "__tuple__" in value:
        return tuple(decode(item) for item in value["__tuple__"])
    if "__enum__" in value:
        name, raw = value["__enum__"].split(":", 1)
        return getattr(models, name)(raw)
    if "__type__" in value:
        cls = getattr(models, value["__type__"])
        return cls(**{key: decode(item) for key, item in value.items() if key != "__type__"})
    return {key: decode(item) for key, item in value.items()}


class NarrativeExporter:
    def write(self, value, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(encode(value), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read(self, path: Path) -> NarrativeResult:
        value = self.read_any(path)
        if not isinstance(value, NarrativeResult):
            raise ValueError("JSON is not a NarrativeResult")
        return value

    def read_input(self, path: Path) -> NarrativeInput:
        value = self.read_any(path)
        if not isinstance(value, NarrativeInput):
            raise ValueError("JSON is not a NarrativeInput")
        return value

    @staticmethod
    def read_any(path: Path):
        value = decode(json.loads(path.read_text(encoding="utf-8")))
        # V7.0 tagged JSON remains the canonical schema. This branch permits
        # a public untagged NarrativeInput snapshot without changing that schema.
        if isinstance(value, dict) and {"target_address", "conclusion_facts", "evidence_index"} <= value.keys():
            fields = NarrativeInput.__dataclass_fields__
            migrated = {key: item for key, item in value.items() if key in fields}
            return NarrativeInput(**migrated)
        return value
