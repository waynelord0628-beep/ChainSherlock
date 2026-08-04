from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from crypto_investigator.importers.mapping import ColumnMapping


@dataclass(frozen=True, slots=True)
class ImportBatch:
    """Canonical raw rows produced by an importer before validation."""

    source: Path
    records: tuple[dict[str, Any], ...]
    column_mapping: ColumnMapping


class Importer(Protocol):
    def load(
        self,
        path: Path,
        column_overrides: Mapping[str, str] | None = None,
    ) -> ImportBatch:
        """Load external data without normalizing it into domain entities."""

