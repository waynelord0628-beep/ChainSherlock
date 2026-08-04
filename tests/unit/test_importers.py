from pathlib import Path

from openpyxl import Workbook
import pandas as pd
import pytest

from crypto_investigator.importers.csv_importer import CsvImporter
from crypto_investigator.importers.excel_importer import ExcelImporter
from crypto_investigator.importers.factory import ImporterFactory
from crypto_investigator.importers.mapping import ColumnMappingError, MappingEngine


HEADERS = ["from", "to", "amount", "asset", "timestamp", "hash"]
ETH_FROM = "0x1111111111111111111111111111111111111111"
ETH_TO = "0x2222222222222222222222222222222222222222"


def test_mapping_recognizes_english_aliases():
    mapping = MappingEngine().resolve(HEADERS)
    assert mapping.canonical_to_source["from_address"] == "from"
    assert mapping.canonical_to_source["tx_hash"] == "hash"


def test_mapping_recognizes_chinese_aliases():
    mapping = MappingEngine().resolve(["來源地址", "接收地址", "金額", "asset", "日期", "txid"])
    assert mapping.canonical_to_source["from_address"] == "來源地址"
    assert mapping.canonical_to_source["amount"] == "金額"


def test_mapping_lists_ambiguous_candidates():
    with pytest.raises(ColumnMappingError) as captured:
        MappingEngine().resolve(["from", "sender", "to", "amount", "timestamp", "hash"])
    assert captured.value.candidates["from_address"] == ("from", "sender")


def test_mapping_honors_explicit_override():
    mapping = MappingEngine().resolve(
        ["from", "sender", "to", "amount", "timestamp", "hash"],
        {"from_address": "sender"},
    )
    assert mapping.canonical_to_source["from_address"] == "sender"


def test_mapping_reports_missing_required_fields():
    with pytest.raises(ColumnMappingError) as captured:
        MappingEngine().resolve(["from", "to"])
    assert set(captured.value.missing) == {"amount", "timestamp", "tx_hash"}


def test_csv_import(tmp_path: Path):
    csv_file = tmp_path / "transactions.csv"
    csv_file.write_text(
        ",".join(HEADERS) + f"\n{ETH_FROM},{ETH_TO},1.5,ETH,2026-01-01,0xabc\n",
        encoding="utf-8",
    )
    batch = CsvImporter().load(csv_file)
    assert batch.records[0]["amount"] == "1.5"
    assert batch.records[0]["asset_symbol"] == "ETH"


def test_excel_xlsx_import_preserves_formula_for_validation(tmp_path: Path):
    excel_file = tmp_path / "transactions.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append([ETH_FROM, ETH_TO, "=1+1", "ETH", "2026-01-01", "0xabc"])
    workbook.save(excel_file)
    batch = ExcelImporter().load(excel_file)
    assert batch.records[0]["amount"] == "=1+1"


def test_excel_xls_import_uses_xlrd(tmp_path: Path, monkeypatch):
    excel_file = tmp_path / "transactions.xls"
    excel_file.write_bytes(b"test fixture placeholder")
    frame = pd.DataFrame(
        [[ETH_FROM, ETH_TO, "1", "ETH", "2026-01-01", "0xabc"]],
        columns=HEADERS,
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: frame)
    batch = ExcelImporter().load(excel_file)
    assert batch.records[0]["tx_hash"] == "0xabc"


@pytest.mark.parametrize("suffix", [".csv", ".xls", ".xlsx"])
def test_importer_factory_supports_required_formats(suffix: str):
    assert ImporterFactory.create(Path("input" + suffix)) is not None


def test_importer_factory_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unsupported file format"):
        ImporterFactory.create(Path("input.json"))
