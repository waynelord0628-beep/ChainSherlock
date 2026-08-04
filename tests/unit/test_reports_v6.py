from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from types import SimpleNamespace

import pytest
import reportlab

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.domain.transaction import Chain, Transaction
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.evidence import EvidenceManifest
from crypto_investigator.reports.errors import PdfExportError, ReportComposeError, ReportSecurityError
from crypto_investigator.reports.export import ReportExportCoordinator
from crypto_investigator.reports.factory import ReportFactory
from crypto_investigator.reports.formatting import redact, safe_output_path, validate_output_directory
from crypto_investigator.reports.html_exporter import HtmlReportExporter
from crypto_investigator.reports.json_exporter import read_report_data, write_report_data
from crypto_investigator.reports.markdown_exporter import MarkdownReportExporter
from crypto_investigator.reports.pdf_exporter import PdfReportExporter


TARGET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40


@pytest.fixture
def analysis():
    transactions = (
        Transaction(
            chain=Chain.ETHEREUM,
            tx_hash="0x1",
            from_address=TARGET,
            to_address=OTHER,
            asset_symbol="USDT",
            amount=Decimal("1.123456789012345678"),
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        ),
        Transaction(
            chain=Chain.ETHEREUM,
            tx_hash="0x2",
            from_address=OTHER,
            to_address=TARGET,
            asset_symbol="ETH",
            amount=Decimal("2.000000000000000001"),
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
        ),
    )
    return AnalysisEngine().analyze(transactions, TARGET)


@pytest.fixture
def document(analysis):
    return ReportComposer().compose(
        analysis,
        target_address=TARGET,
        chain="ethereum",
        report_id="CSR-TEST",
    )


@pytest.mark.parametrize(
    "attribute",
    [
        "report_id", "generated_at", "report_version", "chain", "target_address",
        "target_type", "source_type", "source_files", "providers",
        "analysis_completeness", "graph_completeness", "transaction_count",
        "rejected_record_count", "warning_count", "timezone", "language",
        "output_directory",
    ],
)
def test_report_metadata_fields(document, attribute):
    assert hasattr(document.metadata, attribute)


@pytest.mark.parametrize(
    "section_id",
    [
        "cover", "executive_summary", "target", "data_sources", "completeness",
        "analysis_summary", "asset_flows", "observations", "limitations",
        "conclusion", "evidence_index", "appendix",
    ],
)
def test_required_report_sections(document, section_id):
    assert section_id in {section.section_id for section in document.sections}


@pytest.mark.parametrize("report_type", ["address_report", "transaction_report", "file_report"])
def test_report_factory_types(report_type):
    assert isinstance(ReportFactory.create(report_type), ReportComposer)


def test_report_factory_unknown_type():
    with pytest.raises(ReportComposeError):
        ReportFactory.create("unknown")


def test_json_round_trip_preserves_document(document, tmp_path):
    path = write_report_data(document, tmp_path / "report_data.json")
    assert read_report_data(path) == document


@pytest.mark.parametrize(
    "payload",
    [
        "api_key=secret", "api-key: secret", "token=secret",
        "Authorization: Bearer-secret", "apikey=secret&x=1",
        r"C:\Users\person\secret.txt", "/home/person/secret.txt",
    ],
)
def test_secret_and_path_redaction(payload):
    cleaned = redact(payload)
    assert "secret" not in cleaned
    assert "person" not in cleaned


@pytest.mark.parametrize("filename", ["report.md", "report.html", "report.docx", "report.pdf"])
def test_safe_output_filename(tmp_path, filename):
    assert safe_output_path(tmp_path, filename).parent == tmp_path.resolve()


@pytest.mark.parametrize("filename", ["../outside", "../../outside", r"..\outside"])
def test_output_filename_traversal_rejected(tmp_path, filename):
    with pytest.raises(ReportSecurityError):
        safe_output_path(tmp_path, filename)


def test_output_directory_traversal_rejected():
    with pytest.raises(ReportSecurityError):
        validate_output_directory(Path("output/../../outside"))


def test_evidence_manifest_sha256_and_relative_path(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes(b"a,b\n1,2\n")
    evidence = EvidenceManifest().collect((source,), root=tmp_path)
    assert evidence[0].hash == hashlib.sha256(source.read_bytes()).hexdigest()
    assert evidence[0].source_reference == "source.csv"


def test_evidence_manifest_skips_missing_file(tmp_path):
    assert EvidenceManifest().collect((tmp_path / "missing.csv",), root=tmp_path) == ()


def test_markdown_export_utf8_and_citations(document, tmp_path):
    path = MarkdownReportExporter().write(document, tmp_path / "report.md")
    assert "ChainSherlock" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("marker", ["@media print", "<style", "Evidence Index"])
def test_html_is_offline_printable(document, tmp_path, marker):
    content = HtmlReportExporter().write(document, tmp_path / "report.html").read_text(encoding="utf-8")
    assert marker in content
    assert "https://" not in content


@pytest.mark.parametrize(
    "payload",
    ["<script>alert(1)</script>", '<img src=x onerror="alert(1)">', "<svg onload=alert(1)>"],
)
def test_html_escapes_untrusted_title(analysis, tmp_path, payload):
    document = ReportComposer().compose(analysis, title=payload)
    content = HtmlReportExporter().write(document, tmp_path / "report.html").read_text(encoding="utf-8")
    assert payload not in content


def test_docx_export_is_readable_zip(document, tmp_path):
    path = ReportExportCoordinator().export(document, tmp_path, "docx")
    with ZipFile(tmp_path / path.files["docx"]) as archive:
        assert "word/document.xml" in archive.namelist()


def test_pdf_requires_cjk_font(document, tmp_path, monkeypatch):
    monkeypatch.delenv("CHAINSHERLOCK_PDF_CJK_FONT", raising=False)
    monkeypatch.delenv("WINDIR", raising=False)
    with pytest.raises(PdfExportError):
        PdfReportExporter().write(document, tmp_path / "report.pdf")


def test_pdf_failure_retains_other_formats(document, tmp_path, monkeypatch):
    monkeypatch.delenv("CHAINSHERLOCK_PDF_CJK_FONT", raising=False)
    monkeypatch.delenv("WINDIR", raising=False)
    result = ReportExportCoordinator().export(document, tmp_path, "all")
    assert result.status == "partial"
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "report.docx").exists()


def test_pdf_uses_windows_system_font_without_path_disclosure(
    document, tmp_path, monkeypatch
):
    monkeypatch.delenv("CHAINSHERLOCK_PDF_CJK_FONT", raising=False)
    windows = tmp_path / "Windows"
    fonts = windows / "Fonts"
    fonts.mkdir(parents=True)
    source = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    (fonts / "kaiu.ttf").write_bytes(source.read_bytes())
    monkeypatch.setenv("WINDIR", str(windows))

    result = ReportExportCoordinator().export(document, tmp_path / "output", "pdf")

    assert result.status == "complete"
    status = json.loads(
        (tmp_path / "output" / "export_status.json").read_text(encoding="utf-8")
    )
    assert status["pdf_font"] == {
        "available": True,
        "font_name": "標楷體",
        "source": "system",
    }
    assert str(windows) not in json.dumps(status, ensure_ascii=False)


@pytest.mark.parametrize("requested", ["markdown", "html", "docx"])
def test_single_export_status_complete(document, tmp_path, requested):
    result = ReportExportCoordinator().export(document, tmp_path, requested)
    assert result.status == "complete"
    assert (tmp_path / "report_data.json").exists()
    assert (tmp_path / "evidence_manifest.json").exists()


@pytest.mark.parametrize("language,expected", [("zh-TW", "zh-TW"), ("en-US", "en-US"), ("xx", "zh-TW")])
def test_language_selection(analysis, language, expected):
    document = ReportComposer().compose(analysis, language=language)
    assert document.metadata.language == expected


@pytest.mark.parametrize("asset", ["USDT", "ETH"])
def test_assets_remain_separated(document, asset):
    section = next(item for item in document.sections if item.section_id == "asset_flows")
    assert asset in {row[0] for row in section.tables[0].rows}


@pytest.mark.parametrize("value", ["1.123456789012345678", "2.000000000000000001"])
def test_decimal_precision_is_preserved(document, value):
    section = next(item for item in document.sections if item.section_id == "asset_flows")
    assert value in {cell for row in section.tables[0].rows for cell in row}


@pytest.mark.parametrize("word", ["洗錢地址", "詐騙集團", "確定屬於犯罪組織", "已證明犯罪意圖"])
def test_conclusion_has_no_criminal_determination(document, word):
    assert word not in document.conclusion.text


def test_graph_metadata_composition(analysis):
    graph = GraphBuilder().build(analysis, chain=Chain.ETHEREUM, target_address=TARGET)
    document = ReportComposer().compose(analysis, graph=graph)
    assert "graph" in {section.section_id for section in document.sections}


@pytest.mark.parametrize("section_id", ["provider_status", "provider_errors", "rejected_records"])
def test_empty_optional_sections_are_omitted(document, section_id):
    assert section_id not in {section.section_id for section in document.sections}


def test_export_status_files_are_valid_json(document, tmp_path):
    ReportExportCoordinator().export(document, tmp_path, "markdown")
    assert json.loads((tmp_path / "export_status.json").read_text(encoding="utf-8"))["status"] == "complete"
    assert json.loads((tmp_path / "export_errors.json").read_text(encoding="utf-8")) == []


def test_public_analysis_json_mapping_preserves_summary_and_assets(analysis):
    from crypto_investigator.analyzers.export import AnalysisExporter

    value = AnalysisExporter.to_primitive(analysis)
    document = ReportComposer().compose(value, target_address=TARGET, chain="ethereum")
    summary = next(item for item in document.sections if item.section_id == "analysis_summary")
    assets = next(item for item in document.sections if item.section_id == "asset_flows")
    assert ("Analysis 交易數", "2") in summary.tables[0].rows
    assert {row[0] for row in assets.tables[0].rows} == {"ETH", "USDT"}


def test_completeness_discloses_zero_provider_errors_and_rejections(document):
    section = next(item for item in document.sections if item.section_id == "completeness")
    assert "Provider 錯誤：0 筆。" in section.content_blocks
    assert "被拒絕資料：0 筆。" in section.content_blocks


@pytest.mark.parametrize(
    "payload,unsafe",
    [
        ("<script>alert(1)</script>", "<script>"),
        ("<img src=x onerror=alert(1)>", "<img"),
        ("../../outside", "../../"),
        ("api_key=fake-secret", "fake-secret"),
    ],
)
def test_report_text_security_normalization(payload, unsafe):
    assert unsafe not in redact(payload)


def test_formula_like_text_is_neutralized():
    assert redact("=HYPERLINK('x')").startswith("'=")


def test_markdown_table_rows_have_line_breaks(document, tmp_path):
    content = MarkdownReportExporter().write(document, tmp_path / "report.md").read_text(encoding="utf-8")
    assert "| Analysis 交易數 | 2 |" in content


def test_docx_contains_font_and_page_number_settings(document, tmp_path):
    ReportExportCoordinator().export(document, tmp_path, "docx")
    with ZipFile(tmp_path / "report.docx") as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        styles_xml = archive.read("word/styles.xml").decode("utf-8")
        footer_xml = b"".join(
            archive.read(name) for name in archive.namelist() if name.startswith("word/footer")
        ).decode("utf-8")
    assert "Times New Roman" in styles_xml
    assert "標楷體" in styles_xml
    assert "Consolas" in document_xml
    assert 'w:instr="PAGE"' in footer_xml


def test_pdf_has_page_number_and_valid_page(document, tmp_path):
    font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    path = PdfReportExporter().write(document, tmp_path / "report.pdf", font)
    content = path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"/Type /Page" in content


def test_malicious_content_is_safe_in_every_export(analysis, tmp_path, monkeypatch):
    payload = (
        "<script>alert(1)</script> "
        "<img src=x onerror=alert(1)> "
        "=HYPERLINK('x') ../../outside api_key=fake-secret"
    )
    document = ReportComposer().compose(analysis, title=payload)
    font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    monkeypatch.setenv("CHAINSHERLOCK_PDF_CJK_FONT", str(font))
    result = ReportExportCoordinator().export(document, tmp_path, "all")
    assert result.status == "complete"
    text_outputs = (
        (tmp_path / "report.md").read_text(encoding="utf-8"),
        (tmp_path / "report.html").read_text(encoding="utf-8"),
        (tmp_path / "report_data.json").read_text(encoding="utf-8"),
    )
    with ZipFile(tmp_path / "report.docx") as archive:
        docx_xml = archive.read("word/document.xml").decode("utf-8")
    for content in (*text_outputs, docx_xml):
        assert "<script>" not in content
        assert "<img src=x" not in content
        assert "../../outside" not in content
        assert "fake-secret" not in content
    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF-")
