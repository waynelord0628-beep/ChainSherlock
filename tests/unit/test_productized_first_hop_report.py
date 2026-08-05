from dataclasses import replace
from datetime import UTC, datetime

from crypto_investigator.reports.forensic_artifacts import write_forensic_artifacts
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
from crypto_investigator.reports.presentation import format_display_text


TARGET = "TUxHyMSwPWRUGS7PH25VXtsQHUkwZdq95n"
SOURCE = "TQRVyCsFJREqF1D7FsPrmCHR9EbYZ71eu1"
DESTINATION = "TNfV9YZxoJvrcyEuT9GXqpgdpXLb2T81eU"


def _asset(asset, role, incoming, outgoing, excluded=0):
    return {
        "asset": asset,
        "role": role,
        "transaction_count": 10,
        "material_transaction_count": 8,
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


def test_productized_sections_focus_on_usdt_and_trx():
    sections = build_productized_sections(
        _document(),
        {TARGET: "地址-001", SOURCE: "地址-002", DESTINATION: "地址-003"},
    )
    facts = next(item for item in sections if item.section_id == "product_asset_facts")
    rendered = " ".join(cell for row in facts.tables[0].rows for cell in row)
    assert "USDT" in rendered
    assert "TRX" in rendered
    assert "unknown_tron_asset" not in rendered


def test_productized_amounts_are_rounded_to_two_decimals():
    sections = build_productized_sections(_document(), {})
    structure = next(
        item for item in sections if item.section_id == "benchmark_usdt_structure"
    )
    rendered = " ".join(cell for table in structure.tables for row in table.rows for cell in row)
    assert "11,216,092.56 USDT" in rendered
    assert "11,204,714.61 USDT" in rendered
    assert "11216092.558159" not in rendered


def test_only_top_three_first_hop_candidates_become_cards():
    sections = build_productized_sections(_document(), {})
    candidates = next(item for item in sections if item.section_id == "first_hop_candidates")
    assert len(candidates.tables) == 3
    assert all(len(table.columns) == 2 for table in candidates.tables)


def test_front_registry_has_six_readable_columns():
    raw = ReportSection(
        "address_registry",
        "raw",
        22,
        tables=(
            ReportTable(
                "address_registry_identity",
                "raw",
                tuple(str(index) for index in range(7)),
                (
                    (
                        "地址-001",
                        "TRON",
                        TARGET,
                        "未標記",
                        "候選角色未確認",
                        "請見正文",
                        "技術附錄",
                    ),
                ),
            ),
        ),
    )
    normalized = normalize_address_registry(raw, _document())
    assert normalized.tables[0].columns == (
        "地址編號",
        "完整地址",
        "鏈別",
        "主要角色",
        "主要資產",
        "Label",
    )
    assert normalized.tables[0].rows[0][1] == TARGET
    assert normalized.tables[0].rows[0][3] == "調查標的"


def test_non_material_artifacts_are_external_and_reversible(tmp_path):
    files = write_forensic_artifacts(_document(), tmp_path)
    assert files["non_material_assets"] == "non_material_assets.csv"
    assert files["technical_exclusions"] == "technical_exclusions.json"
    content = (tmp_path / "technical_exclusions.json").read_text(encoding="utf-8")
    assert '"raw_evidence_modified": false' in content
    assert '"reversible": true' in content


def test_productized_main_sections_do_not_render_none_or_raw_unknown_enum():
    sections = build_productized_sections(_document(), {})
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
