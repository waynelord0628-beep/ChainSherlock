from crypto_investigator.reports.pdf_exporter import (
    PdfReportExporter,
    pdf_typography_status,
)
from crypto_investigator.reports.typography import (
    CJK_FONT,
    LATIN_FONT,
    TABLE_LATIN_FONT,
    ScriptRole,
    font_family,
    mixed_script_runs,
)


def test_mixed_body_text_assigns_cjk_latin_and_numeric_roles():
    runs = mixed_script_runs("地址-001 收受 7,416,900.00 USDT")
    assert [(run.text, run.role) for run in runs] == [
        ("地址-", ScriptRole.CJK),
        ("001 ", ScriptRole.NUMERIC),
        ("收受 ", ScriptRole.CJK),
        ("7,416,900.00 ", ScriptRole.NUMERIC),
        ("USDT", ScriptRole.LATIN),
    ]


def test_mixed_table_text_uses_consolas_for_latin_but_times_for_numbers():
    runs = mixed_script_runs("資產 USDT 7,416,900.00", table=True)
    assert [run.role for run in runs] == [
        ScriptRole.CJK,
        ScriptRole.TABLE_TECH,
        ScriptRole.NUMERIC,
    ]
    assert font_family(ScriptRole.CJK, table=True) == CJK_FONT
    assert font_family(ScriptRole.TABLE_TECH, table=True) == TABLE_LATIN_FONT
    assert font_family(ScriptRole.NUMERIC, table=True) == LATIN_FONT


def test_pdf_styled_text_splits_mixed_table_runs_by_font():
    exporter = PdfReportExporter()
    exporter._cjk_font_name = "CJK"
    exporter._latin_font_name = "Times"
    exporter._table_font_name = "Consolas"
    rendered = exporter._styled_text("地址-001 USDT 25.00", "Consolas")
    assert '<font name="CJK">地址-</font>' in rendered
    assert '<font name="Times">001 </font>' in rendered
    assert '<font name="Consolas">USDT </font>' in rendered
    assert '<font name="Times">25.00</font>' in rendered


def test_cjk_punctuation_after_latin_uses_cjk_font():
    runs = mixed_script_runs("標示為 verified。")
    assert runs[-1].text == "。"
    assert runs[-1].role is ScriptRole.CJK


def test_pdf_typography_status_contains_no_local_font_paths():
    status = pdf_typography_status()
    assert set(status) == {"cjk", "latin_numeric", "table_latin"}
    serialized = str(status)
    assert "C:\\" not in serialized
    assert ".ttf" not in serialized
