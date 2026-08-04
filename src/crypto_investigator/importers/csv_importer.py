from pathlib import Path
from typing import Mapping

from charset_normalizer import from_bytes
import pandas as pd

from crypto_investigator.importers.base import ImportBatch
from crypto_investigator.importers.mapping import MappingEngine


class CsvImporter:
    def __init__(self, mapping_engine: MappingEngine | None = None) -> None:
        self.mapping_engine = mapping_engine or MappingEngine()

    def load(
        self,
        path: Path,
        column_overrides: Mapping[str, str] | None = None,
    ) -> ImportBatch:
        raw = path.read_bytes()
        best_match = from_bytes(raw).best()
        encoding = best_match.encoding if best_match is not None else "utf-8"
        frame = pd.read_csv(path, dtype=object, encoding=encoding, keep_default_na=False)
        mapping = self.mapping_engine.resolve(frame.columns, column_overrides)
        records = tuple(
            mapping.apply(self._clean_row(row)) for row in frame.to_dict(orient="records")
        )
        return ImportBatch(path, records, mapping)

    @staticmethod
    def _clean_row(row: dict[str, object]) -> dict[str, object]:
        return {
            key: None if pd.isna(value) or value == "" else value
            for key, value in row.items()
        }

