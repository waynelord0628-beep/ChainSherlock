from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
import zipfile

import pytest

from crypto_investigator.cli import _provider_scope
from crypto_investigator.domain.scope import PaginationPolicy, ScopeType
from crypto_investigator.reports.docx_exporter import DocxReportExporter
from crypto_investigator.reports.html_exporter import HtmlReportExporter
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.formatting import (
    abbreviate_identifier,
    format_amount,
    format_duration,
    format_percent,
)
from crypto_investigator.reports.models import (
    ReportEvidence,
    ReportSection,
    ReportTable,
)
from crypto_investigator.reports.presentation import (
    format_display_text,
    prepare_report_for_display,
)


ADDRESS = "TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE"
OTHER = "TGxVDjGujrUXQGZtWgNcdeawkPYeoE4Frv"


def _analysis():
    return {
        "summary": {
            "first_seen": "2026-01-05T03:31:27+00:00",
            "last_seen": "2026-01-06T03:31:27+00:00",
            "transaction_count": 1000,
            "incoming_count": 415,
            "outgoing_count": 477,
            "unique_counterparties": 12,
        },
        "statistics": {
            "incoming_amount": {"USDT": Decimal("1234567.89"), "0597 COM": Decimal("0.01")},
            "outgoing_amount": {"USDT": Decimal("1200000"), "0597 COM": Decimal("0")},
            "asset_breakdown": {
                "USDT": {"transaction_count": 999},
                "0597 COM": {"transaction_count": 1},
            },
        },
        "counterparties": [{
            "address": OTHER,
            "incoming_count": 2,
            "outgoing_count": 8,
            "interaction_count": 10,
            "incoming_amount_by_asset": {"USDT": Decimal("100")},
            "outgoing_amount_by_asset": {"USDT": Decimal("900")},
            "first_seen": "2026-01-05T03:31:27+00:00",
            "last_seen": "2026-01-06T03:31:27+00:00",
        }],
        "timeline": {},
        "metadata": {
            "completeness": "partial",
            "analysis_scope": {
                "scope_type": "full_history",
                "timezone": "Asia/Taipei",
            },
            "time_scope": {"full_history_complete": False},
        },
        "warnings": [],
    }


def _investigation():
    return {
        "structured_metadata": {
            "source_transaction_count": 1000,
            "assets": ["USDT"],
        },
        "direction_reconciliation": {
            "failed_transaction_count": 0,
            "unclassified_direction_count": 108,
        },
        "funding": {
            "sources": [{
                "address": ADDRESS,
                "amounts_by_asset": {"USDT": "291166.569"},
                "share_by_asset": {"USDT": "0.291166569"},
                "first_funding": "2026-01-05T03:31:27+00:00",
                "last_funding": "2026-01-06T03:31:27+00:00",
            }],
            "transitions": [],
            "top_sources_by_asset": {"USDT": [ADDRESS]},
            "concentration_by_asset": {},
        },
        "distribution_analysis": {"statistics_by_asset": {
            "USDT": {
                "matched_incoming_amount": "100",
                "matched_outgoing_amount": "90",
                "unmatched_incoming_amount": "10",
                "unmatched_outgoing_amount": "5",
                "average_holding_seconds": "86254.5",
                "median_holding_seconds": "248397",
                "within_1_hour_ratio": "0.1",
                "within_24_hours_ratio": "0.75",
                "pass_through_event_count": 8,
            }
        }},
        "stages": [{
            "stage": "dominant",
            "started_at": "2026-01-05T03:31:27+00:00",
            "ended_at": "2026-01-06T03:31:27+00:00",
            "transaction_count": 100,
            "assets": ["USDT"],
            "dominant_funding_sources": [ADDRESS],
            "dominant_outgoing_counterparties": [OTHER],
            "reason_codes": ["frequency_increased"],
        }],
        "dormant_periods": [],
        "transfer_patterns": {
            "integer_amount_ratio": "0.75",
            "batch_incoming_count": 4,
            "batch_outgoing_count": 49,
            "fixed_amounts": {"USDT": [500, 1000, 2000]},
            "amount_suffix_counts": {"00": 400},
        },
        "services": [],
        "observations": [{
            "code": "funding_source_changed",
            "factual_statement": "主要供款方於 2026-01-05T03:31:27+00:00 改變。",
            "evidence_refs": ["OBS-001"],
        }],
        "conclusion_fact_items": [{
            "fact_code": "provider_truncated",
            "value": True,
            "evidence_refs": ["FACT-003"],
        }],
        "evidence_refs": [{"evidence_id": "IF0"}],
    }


def _document():
    return ReportComposer().compose(
        _analysis(),
        investigation=_investigation(),
        target_address=ADDRESS,
        chain="tron",
        provider_status=({
            "chain": "tron",
            "capability": "token_transfers",
            "provider": "trongrid",
            "fetched_records": 1000,
            "completeness": "partial",
            "truncated": True,
            "truncation_reason": "safety_limit",
            "warnings": ["仍有更多資料"],
            "analysis_completeness": "internal",
            "fallback_attempted": True,
        },),
        materiality_thresholds={"0597 COM": Decimal("1")},
    )


def _section(document, section_id):
    return next(item for item in document.sections if item.section_id == section_id)


def test_01_provider_table_has_eight_columns():
    assert len(_section(_document(), "provider_status").tables[0].columns) == 8


def test_02_provider_engineering_columns_are_absent():
    columns = _section(_document(), "provider_status").tables[0].columns
    assert "analysis_completeness" not in columns
    assert "fallback_attempted" not in columns


def test_03_counterparty_table_has_no_duplicate_count_columns():
    columns = _section(_document(), "outgoing_distribution").tables[0].columns
    assert columns.count("交易次數") == 1
    assert "incoming_count" not in columns


def test_04_main_address_has_registry_id_and_full_value():
    display = prepare_report_for_display(_document())
    row = _section(display, "outgoing_distribution").tables[0].rows[0]
    assert row[1].startswith("ADDR-")
    assert row[2] == OTHER


def test_05_full_address_is_preserved_in_appendix():
    display = prepare_report_for_display(_document())
    table = next(
        table
        for table in _section(display, "appendix").tables
        if table.table_id == "address_registry_identity"
    )
    assert any(OTHER in row for row in table.rows)


def test_06_python_dict_repr_is_absent_from_main_tables():
    rendered = str([table.rows for section in _document().sections for table in section.tables])
    assert "{'" not in rendered


def test_07_python_list_repr_is_absent_from_pattern_table():
    table = _section(_document(), "transfer_patterns").tables[0]
    assert "[" not in str(table.rows)


def test_08_ratio_is_rendered_as_percentage():
    table = _section(_document(), "funding_analysis").tables[0]
    assert table.rows[0][4] == "29.12%"


def test_09_amount_uses_grouping_without_losing_precision():
    assert format_amount("1234567.89") == "1,234,567.89"


def test_10_duration_under_one_day_is_human_readable():
    assert format_duration("86254.5") == "23 小時 57 分"


def test_11_duration_over_one_day_is_human_readable():
    assert format_duration("248397") == "2 天 20 小時 59 分"


def test_12_utc_is_converted_to_taipei():
    assert format_display_text(
        "2026-01-05T03:31:27+00:00", "Asia/Taipei"
    ) == "2026-01-05 11:31:27"


def test_13_naive_datetime_is_marked_unknown():
    assert "timezone unknown" in format_display_text(
        "2026-01-05T03:31:27", "Asia/Taipei"
    )


def test_14_metadata_uses_case_timezone():
    assert _document().metadata.timezone == "Asia/Taipei"


def test_15_cover_declares_taipei_timezone():
    assert "UTC+8（Asia/Taipei）" in " ".join(
        _section(_document(), "cover").content_blocks
    )


def test_16_display_generated_at_uses_taipei_offset():
    document = replace(
        _document(),
        metadata=replace(
            _document().metadata,
            generated_at=datetime(2026, 1, 5, 3, 31, 27, tzinfo=UTC),
        ),
    )
    assert prepare_report_for_display(document).metadata.generated_at.hour == 11


def test_17_ai_enrichment_datetime_text_uses_taipei():
    document = _document()
    extra = ReportSection(
        "ai_test", "AI 專業綜合", 30,
        ("發生時間 2026-01-05T03:31:27+00:00。",),
    )
    display = prepare_report_for_display(
        replace(document, sections=(*document.sections, extra))
    )
    assert "2026-01-05 11:31:27" in _section(display, "ai_test").content_blocks[0]


def test_18_evidence_index_is_artifact_level():
    table = _section(_document(), "evidence_index").tables[0]
    assert table.columns == (
        "Evidence ID", "檔名", "類型", "SHA-256", "完整性", "來源", "備註"
    )


def test_19_record_level_if_id_is_not_in_evidence_index():
    table = _section(_document(), "evidence_index").tables[0]
    assert not any(cell.startswith("IF") for row in table.rows for cell in row)


def test_20_legacy_evidence_is_not_marked_verified():
    row = _section(_document(), "evidence_index").tables[0].rows[0]
    assert row[3] == "雜湊不可用"
    assert row[4] == "無法驗證"


def test_21_ai_section_order_precedes_evidence_index():
    document = _document()
    ai = ReportSection("ai_conclusion", "AI 專業綜合", 30, ("內容",))
    ordered = sorted((*document.sections, ai), key=lambda item: (item.order, item.section_id))
    assert [item.section_id for item in ordered].index("ai_conclusion") < [
        item.section_id for item in ordered
    ].index("evidence_index")


def test_22_display_tables_are_limited_to_ten_columns():
    document = _document()
    wide = ReportTable(
        "wide", "wide", tuple(f"c{i}" for i in range(12)),
        (tuple(str(i) for i in range(12)),),
    )
    extra = ReportSection("wide", "wide", 40, tables=(wide,))
    display = prepare_report_for_display(
        replace(document, sections=(*document.sections, extra))
    )
    assert all(
        len(table.columns) <= 6 for table in _section(display, "wide").tables
    )
    assert len(_section(display, "wide").tables) == 3


def test_23_all_composed_main_tables_have_at_most_ten_columns():
    assert max(
        len(table.columns)
        for section in _document().sections
        for table in section.tables
    ) <= 10


def test_24_non_material_asset_is_moved_to_appendix():
    assert "0597 COM" not in {
        row[0] for row in _section(_document(), "asset_flows").tables[0].rows
    }
    assert "0597 COM" in {
        row[0] for row in _section(_document(), "non_material_assets").tables[0].rows
    }


def test_25_percentage_formatter_is_stable():
    assert format_percent("0.291166569") == "29.12%"


def test_26_formal_full_history_is_unbounded():
    settings = SimpleNamespace(
        pagination=SimpleNamespace(max_pages=1, max_records=50)
    )
    scope = _provider_scope(
        ScopeType.FULL_HISTORY, None, None,
        timezone="Asia/Taipei", settings=settings,
    )
    assert scope.pagination_policy is PaginationPolicy.TO_PROVIDER_END
    assert scope.max_pages is None
    assert scope.max_records is None


def test_27_quick_preview_is_explicitly_bounded():
    settings = SimpleNamespace(
        pagination=SimpleNamespace(max_pages=1, max_records=500)
    )
    scope = _provider_scope(
        ScopeType.QUICK_PREVIEW, None, None,
        timezone="Asia/Taipei", settings=settings,
    )
    assert scope.pagination_policy is PaginationPolicy.BOUNDED
    assert scope.max_pages == 1
    assert scope.max_records == 500


def test_28_full_history_rejects_preview_limits():
    settings = SimpleNamespace(
        pagination=SimpleNamespace(max_pages=1, max_records=500)
    )
    with pytest.raises(Exception):
        _provider_scope(
            ScopeType.FULL_HISTORY, 1, 1000,
            timezone="Asia/Taipei", settings=settings,
        )


def test_29_complete_full_history_uses_address_first_seen_label():
    value = _analysis()
    value["metadata"]["completeness"] = "complete"
    value["metadata"]["time_scope"]["full_history_complete"] = True
    document = ReportComposer().compose(value, investigation=_investigation())
    rows = _section(document, "analysis_summary").tables[0].rows
    assert any(row[0] == "地址首次交易時間" for row in rows)


def test_30_asset_time_scope_is_preserved_by_asset():
    value = _analysis()
    value["statistics"]["incoming_amount"]["TRX"] = Decimal("10")
    value["statistics"]["outgoing_amount"]["TRX"] = Decimal("5")
    value["statistics"]["asset_breakdown"]["TRX"] = {"transaction_count": 2}
    value["metadata"]["time_scope"].update({
        "first_seen_by_asset": {
            "TRX": "2025-05-30T16:47:06Z",
            "USDT": "2025-05-30T16:55:36Z",
        },
        "last_seen_by_asset": {
            "TRX": "2026-08-04T15:01:21Z",
            "USDT": "2026-08-04T14:59:15Z",
        },
    })
    table = _section(
        ReportComposer().compose(value, investigation=_investigation()),
        "asset_flows",
    ).tables[1]
    assert ("TRX", "2025-05-31 00:47:06", "2026-08-04 23:01:21") in table.rows
    assert ("USDT", "2025-05-31 00:55:36", "2026-08-04 22:59:15") in table.rows


def test_31_docx_has_repeating_headers_and_non_splitting_rows(tmp_path):
    path = DocxReportExporter().write(
        prepare_report_for_display(_document()), tmp_path / "report.docx"
    )
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "<w:tblHeader" in xml
    assert "<w:cantSplit" in xml
    assert "<w:keepNext" in xml


def test_32_html_print_layout_repeats_headers_and_keeps_rows(tmp_path):
    path = HtmlReportExporter().write(
        prepare_report_for_display(_document()), tmp_path / "report.html"
    )
    content = path.read_text(encoding="utf-8")
    assert "<thead>" in content
    assert "display:table-header-group" in content
    assert "page-break-inside:avoid" in content


def test_33_evidence_index_remains_artifact_level_and_compact():
    table = _section(_document(), "evidence_index").tables[0]
    assert len(table.rows) < 10
    assert all(not row[0].startswith("IF") for row in table.rows)
