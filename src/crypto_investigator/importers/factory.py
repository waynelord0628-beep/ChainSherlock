from pathlib import Path

from crypto_investigator.importers.base import Importer
from crypto_investigator.importers.csv_importer import CsvImporter
from crypto_investigator.importers.excel_importer import ExcelImporter


class ImporterFactory:
    _extensions = {
        ".csv": CsvImporter,
        ".xls": ExcelImporter,
        ".xlsx": ExcelImporter,
    }

    @classmethod
    def create(cls, path: Path) -> Importer:
        importer_type = cls._extensions.get(path.suffix.casefold())
        if importer_type is None:
            raise ValueError(f"Unsupported file format: {path.suffix or '<none>'}")
        return importer_type()

