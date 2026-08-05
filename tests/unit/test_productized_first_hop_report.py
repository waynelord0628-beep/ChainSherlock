from dataclasses import replace
from datetime import UTC, datetime

from crypto_investigator.reports.forensic_artifacts import write_forensic_artifacts
from crypto_investigator.reports.chart_assets import attach_deterministic_chart_assets
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportMetadata,
    ReportSection,
    ReportTable,
)
from crypto_investigator.reports.productized_first_hop import (
    build_productized_sections,
    normalize_address_registry,
)
from crypto_investigator.reports.presentation import (
    address_registry_rows,
    format_display_text,
    prepare_report_for_display,
)


TARGET = "TUxHyMSwPWRUGS7PH25VXtsQHUkwZdq95n"
SOURCE = "TQRVyCsFJREqF1D7FsPrmCHR9EbYZ71eu1"
DESTINATION = "TNfV9YZxoJvrcyEuT9GXqpgdpXLb2T81eU"


def _asset(asset, role, incoming, outgoing, excluded=0):
    return {
        "asset": asset,
        "role": role,
        "transaction_count": 10,
        "material_transaction_count": 8,
        "zero_value_count": 2 if asset == "USDT" else 0,
        "excluded_count": excluded,
        "incoming_count": 5,
        "outgoing_count": 3,
        "incoming_total": incoming,
        "outgoing_total": outgoing,
        "bidirectional_volume": str(float(incoming) + float(outgoing)),
        "net_flow": str(float(incoming) - float(outgoing)),
        "total_nonzero_counterparties": 2,
        "source_concentration": {
            "top_1_share": "0.45",
            "top_5_share": "0.80",
            "top_10_share": "0.90",
        },
        "destination_concentration": {
            "top_1_share": "0.66",
            "top_5_share": "0.85",
            "top_10_share": "0.95",
        },
        "sources": [
            {
                "address": SOURCE,
                "amount": incoming,
                "share": "0.45",
                "transaction_count": 5,
                "label": None,
            }
        ],
        "destinations": [
            {
                "address": DESTINATION,
                "amount": outgoing,
                "share": "0.66",
                "transaction_count": 3,
                "label": None,
            }
        ],
    }


def _document():
    usdt = _asset(
        "USDT",
        "principal_value_asset",
        "11216092.558159",
        "11204714.61",
    )
    trx = _asset("TRX", "operational_asset", "4028.04", "97.12")
    unknown = _asset(
        "unknown_tron_asset",
        "unknown_or_non_value_event",
        "8888.88",
        "0",
        excluded=10,
    )
    product = {
        "retrieval_complete": True,
        "principal_asset": usdt,
        "assets": [usdt, trx, unknown],
        "first_hop_candidates": [
            {
                "candidate_id": f"FH-{index:03d}",
                "address": DESTINATION[:-2] + f"{index:02d}",
                "asset": "USDT",
                "received_amount": str(7_500_000 - index),
                "share_of_target_outflow": "0.66",
                "transaction_count": 10,
                "evidence_refs": [f"tx-{index}"],
                "verification_status": "unverified",
                "onward_data_status": "not_available",
                "priority": "high",
            }
            for index in range(1, 6)
        ],
    }
    metadata = ReportMetadata(
        report_id="TEST",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        chain="tron",
        target_address=TARGET,
        timezone="Asia/Taipei",
        full_history_complete=True,
        provider_raw_record_count=100,
        normalized_record_count=100,
        graph_completeness="complete",
        first_hop_product=product,
    )
    return ReportDocument(
        title="test",
        metadata=metadata,
        sections=(),
        evidence=(),
        citations=(),
        warnings=(),
        limitations=(),
        conclusion=ReportConclusion(completeness="complete", text="test"),
    )


def _registry(document=None):
    document = document or _document()
    return {row[2]: row[0] for row in address_registry_rows(document)}


def test_productized_sections_focus_on_usdt_and_trx():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    facts = next(item for item in sections if item.section_id == "product_asset_facts")
    rendered = " ".join(cell for row in facts.tables[0].rows for cell in row)
    assert "USDT" in rendered
    assert "TRX" in rendered
    assert "unknown_tron_asset" not in rendered


def test_productized_amounts_are_rounded_to_two_decimals():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    structure = next(
        item for item in sections if item.section_id == "benchmark_usdt_structure"
    )
    rendered = " ".join(cell for table in structure.tables for row in table.rows for cell in row)
    assert "11,216,092.56 USDT" in rendered
    assert "11,204,714.61 USDT" in rendered
    assert "11216092.558159" not in rendered


def test_only_top_three_first_hop_candidates_become_cards():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    candidates = next(item for item in sections if item.section_id == "first_hop_candidates")
    assert len(candidates.tables) == 3
    assert all(len(table.columns) == 2 for table in candidates.tables)


def test_front_registry_is_compact_and_separates_role_from_asset():
    document = _document()
    snapshot_rows = address_registry_rows(document)
    raw = ReportSection(
        "address_registry",
        "raw",
        22,
        tables=(
            ReportTable(
                "address_registry_identity",
                "raw",
                tuple(str(index) for index in range(7)),
                snapshot_rows,
            ),
        ),
    )
    normalized = normalize_address_registry(raw, document)
    assert normalized.tables[0].columns == (
        "調查角色",
        "完整地址（地址編號）",
        "資產",
        "流入／流出金額",
        "優先級",
    )
    assert len(normalized.tables[0].rows) <= 10
    assert TARGET in normalized.tables[0].rows[0][1]
    assert normalized.tables[0].rows[0][0] == "調查標的"


def test_usdt_total_nonzero_and_zero_value_counts_are_explicit():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    summary = next(
        item for item in sections if item.section_id == "benchmark_usdt_structure"
    )
    rows = dict(summary.tables[0].rows)
    assert rows["USDT 總紀錄"] == "10 筆"
    assert rows["非零資金移轉"] == "8 筆"
    assert rows["零值合約互動"] == "2 筆"


def test_three_deterministic_chart_sections_are_present():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    ids = {item.section_id for item in sections}
    assert {
        "deterministic_flow_chart",
        "deterministic_monthly_chart",
        "deterministic_destination_chart",
    } <= ids


def test_deterministic_charts_are_real_png_assets(tmp_path):
    document = _document()
    document = replace(
        document,
        sections=build_productized_sections(document, _registry(document)),
    )
    rendered = attach_deterministic_chart_assets(document, tmp_path)
    chart_sections = {
        item.section_id: item
        for item in rendered.sections
        if item.section_id.startswith("deterministic_")
        and item.section_id.endswith("_chart")
    }
    assert len(chart_sections) == 3
    assert all(not item.tables for item in chart_sections.values())
    assert all(item.figures[0].path.endswith(".png") for item in chart_sections.values())
    assert all(
        (tmp_path / item.figures[0].path).read_bytes().startswith(b"\x89PNG")
        for item in chart_sections.values()
    )


def test_single_registry_snapshot_prevents_unnumbered_addresses():
    document = _document()
    display = prepare_report_for_display(document)
    rendered = " ".join(
        cell
        for section in display.sections
        for table in section.tables
        for row in table.rows
        for cell in row
    )
    assert "地址-未編號" not in rendered
    assert sum(section.section_id == "key_addresses" for section in display.sections) == 1
    assert not any(
        section.section_id == "address_registry" for section in display.sections
    )
    assert "淨流量 ÷ USDT 流入總額" in display.conclusion.text


def test_technical_exclusions_do_not_collapse_to_a_false_zero():
    document = replace(
        _document(),
        metadata=replace(
            _document().metadata,
            micro_excluded_count=7,
            unclassified_count=3,
        ),
    )
    sections = build_productized_sections(document, _registry(document))
    technical = next(
        item for item in sections if item.section_id == "technical_exclusions"
    )
    rows = dict((row[0], row[1]) for row in technical.tables[0].rows)
    assert rows["USDT 零值合約互動"] == "2"
    assert rows["低重要性／非核心資產"] == "10"
    assert rows["微額原生資產"] == "7"
    assert rows["未分類技術事件"] == "3"


def test_non_material_artifacts_are_external_and_reversible(tmp_path):
    files = write_forensic_artifacts(_document(), tmp_path)
    assert files["non_material_assets"] == "non_material_assets.csv"
    assert files["technical_exclusions"] == "technical_exclusions.json"
    content = (tmp_path / "technical_exclusions.json").read_text(encoding="utf-8")
    assert '"raw_evidence_modified": false' in content
    assert '"reversible": true' in content


def test_productized_main_sections_do_not_render_none_or_raw_unknown_enum():
    document = _document()
    sections = build_productized_sections(document, _registry(document))
    rendered = " ".join(
        [
            *(
                block
                for section in sections
                for block in section.content_blocks
            ),
            *(
                cell
                for section in sections
                for table in section.tables
                for row in table.rows
                for cell in row
            ),
        ]
    )
    assert "None" not in rendered
    assert "unknown_or_non_value_event" not in rendered


def test_missing_values_use_human_readable_text():
    assert format_display_text(None, "Asia/Taipei") == "資料未保存"
    assert format_display_text("None", "Asia/Taipei") == "資料未保存"
    assert format_display_text("NaN", "Asia/Taipei") == "資料未保存"
