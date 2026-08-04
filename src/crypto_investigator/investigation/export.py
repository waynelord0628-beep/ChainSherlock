from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from crypto_investigator.investigation import investigation_result as models
from crypto_investigator.investigation.errors import InvestigationSerializationError
from crypto_investigator.investigation.investigation_result import InvestigationResult


def _encode(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__type__": type(value).__name__,
            **{field.name: _encode(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    return value


def _decode(value):
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "__decimal__" in value:
        return Decimal(value["__decimal__"])
    if "__datetime__" in value:
        return datetime.fromisoformat(value["__datetime__"])
    if "__tuple__" in value:
        return tuple(_decode(item) for item in value["__tuple__"])
    if "__type__" in value:
        type_name = value["__type__"]
        model = getattr(models, type_name, None)
        if model is None:
            raise InvestigationSerializationError(
                f"Unknown investigation model: {type_name}"
            )
        return model(
            **{
                key: _decode(item)
                for key, item in value.items()
                if key != "__type__"
            }
        )
    return {key: _decode(item) for key, item in value.items()}


class InvestigationExporter:
    def write(self, result: InvestigationResult, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_encode(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def read(self, path: Path) -> InvestigationResult:
        try:
            value = _decode(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as error:
            raise InvestigationSerializationError(
                "Unable to read investigation JSON"
            ) from error
        if not isinstance(value, InvestigationResult):
            raise InvestigationSerializationError("JSON is not an InvestigationResult")
        return value

    def export_all(self, result: InvestigationResult, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        paths = {
            "investigation": self.write(result, output / "investigation.json"),
            "evidence": self._write_value(
                result.evidence_refs, output / "investigation_evidence.json"
            ),
            "observations": self._write_value(
                result.observations, output / "observations.json"
            ),
            "conclusion_facts": self._write_value(
                result.conclusion_fact_items, output / "conclusion_facts.json"
            ),
            "label_matches": self._write_value(
                result.label_matches, output / "label_matches.json"
            ),
        }
        return paths

    @staticmethod
    def _write_value(value, path: Path):
        path.write_text(
            json.dumps(_encode(value), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
