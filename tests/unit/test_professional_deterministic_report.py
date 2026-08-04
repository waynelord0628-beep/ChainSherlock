from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.models import ReportEvidence


def analysis(*, completeness="partial", scope_type="full_history"):
    return {
        "summary": {
            "first_seen": "2025-01-01T00:00:00+00:00",
            "last_seen": "2025-02-01T00:00:00+00:00",
            "transaction_count": 1000,
            "incoming_count": 300,
            "outgoing_count": 700,
            "unique_counterparties": 90,
            "active_days": 30,
            "unconfirmed_count": 2,
            "missing_timestamp_count": 1,
        },
        "statistics": {
            "incoming_amount": {
                "USDT": Decimal("3832964.5679"),
                "DUST": Decimal("0.00001"),
            },
            "outgoing_amount": {
                "USDT": Decimal("3817207.9818"),
                "DUST": Decimal("0"),
            },
            "asset_breakdown": {
                "USDT": {"transaction_count": 1334},
                "DUST": {"transaction_count": 1},
            },
        },
        "counterparties": [
            {
                "address": "Tcandidate",
                "incoming_count": 1,
                "outgoing_count": 20,
                "interaction_count": 21,
                "incoming_amount_by_asset": {"USDT": Decimal("1")},
                "outgoing_amount_by_asset": {"USDT": Decimal("100")},
                "first_seen": "2025-01-01T00:00:00+00:00",
                "last_seen": "2025-02-01T00:00:00+00:00",
            }
        ],
        "timeline": {},
        "metadata": {
            "completeness": completeness,
            "analysis_scope": {
                "scope_type": scope_type,
                "timezone": "Asia/Taipei",
                "date_from": (
                    "2025-01-01T00:00:00+08:00"
                    if scope_type == "custom_date_range"
                    else None
                ),
                "date_to": (
                    "2025-02-01T00:00:00+08:00"
                    if scope_type == "custom_date_range"
                    else None
                ),
            },
            "time_scope": {
                "scope_type": scope_type,
                "full_history_complete": completeness == "complete",
                "overall_first_seen": "2025-01-01T00:00:00+00:00",
                "overall_last_seen": "2025-02-01T00:00:00+00:00",
                "excluded_by_scope": 12,
            },
            "provider_raw_record_count": 1200,
            "normalized_record_count": 1000,
            "analysis_record_count": 1000,
            "rejected_record_count": 20,
            "deduplicated_record_count": 168,
            "excluded_by_scope": 12,
        },
        "warnings": [],
    }


def investigation():
    return {
        "structured_metadata": {
            "source_transaction_count": 808,
            "source_date_from": "2025-01-01T00:00:00+00:00",
            "source_date_to": "2025-02-01T00:00:00+00:00",
            "assets": ["USDT"],
        },
        "direction_reconciliation": {
            "failed_transaction_count": 4,
            "unclassified_direction_count": 8,
        },
        "funding": {
            "sources": [],
            "top_sources_by_asset": {},
            "transitions": [],
            "concentration_by_asset": {},
        },
        "distribution_analysis": {"statistics_by_asset": {}},
        "stages": [],
        "dormant_periods": [],
        "transfer_patterns": {
            "batch_incoming_count": 0,
            "batch_outgoing_count": 0,
            "fixed_amounts": {},
        },
        "services": [
            {
                "address": "Tcandidate",
                "service_type": "possible_payment",
                "label": None,
            }
        ],
        "observations": [],
        "conclusion_fact_items": [
            {
                "fact_code": "graph_truncated",
                "value": False,
                "confidence": "high",
            },
            {
                "fact_code": "provider_truncated",
                "value": False,
                "confidence": "high",
            },
        ],
        "evidence_refs": [{"evidence_id": "IF0"}],
    }


def graph():
    return {
        "nodes": [{}, {}],
        "edges": [{}] * 808,
        "metadata": {
            "included_node_count": 2,
            "included_edge_count": 808,
            "truncated": True,
        },
    }


def section(document, section_id):
    return next(item for item in document.sections if item.section_id == section_id)


def test_partial_full_history_does_not_claim_address_first_seen():
    document = ReportComposer().compose(analysis())
    rows = section(document, "analysis_summary").tables[0].rows
    assert ("目前資料最早時間", "無法確認（歷史資料不完整）") in rows
    assert not any(row[0] == "地址首次交易時間" for row in rows)


def test_custom_range_uses_period_language_and_timezone():
    document = ReportComposer().compose(
        analysis(completeness="complete", scope_type="custom_date_range")
    )
    target = section(document, "target")
    assert "指定分析期間" in " ".join(target.content_blocks)
    assert "Asia/Taipei" in " ".join(target.content_blocks)
    assert any(
        row[0] == "期間內最早交易時間"
        for row in section(document, "analysis_summary").tables[0].rows
    )


def test_pipeline_counts_keep_analysis_and_investigation_separate():
    document = ReportComposer().compose(
        analysis(), graph=graph(), investigation=investigation()
    )
    rows = section(document, "data_pipeline").tables[0].rows
    assert any(row[0] == "Analysis 使用" and row[1] == "1000" for row in rows)
    assert any(
        row[0] == "Investigation 使用交易邊" and row[1] == "808"
        for row in rows
    )


def test_graph_truncated_uses_graph_artifact_as_single_source():
    document = ReportComposer().compose(
        analysis(), graph=graph(), investigation=investigation()
    )
    facts = section(document, "investigation_facts").tables[0].rows
    assert next(row for row in facts if row[0] == "graph_truncated")[1] == "True"


def test_provider_truncated_is_not_graph_truncated():
    document = ReportComposer().compose(
        analysis(),
        graph=graph(),
        investigation=investigation(),
        provider_status=(
            {
                "chain": "tron",
                "capability": "token_transfers",
                "provider": "trongrid",
                "fetched_records": 1000,
                "completeness": "partial",
                "truncated": False,
                "truncation_reason": None,
                "warnings": [],
            },
        ),
    )
    facts = section(document, "investigation_facts").tables[0].rows
    assert next(row for row in facts if row[0] == "provider_truncated")[1] == "False"


def test_provider_table_has_only_human_readable_columns():
    document = ReportComposer().compose(
        analysis(),
        provider_status=(
            {
                "chain": "tron",
                "capability": "token_transfers",
                "provider": "trongrid",
                "fetched_records": 1000,
                "completeness": "partial",
                "truncated": True,
                "truncation_reason": "rate_limit",
                "warnings": ["limited"],
                "private_cursor": "must-not-render",
            },
        ),
    )
    table = section(document, "provider_status").tables[0]
    assert table.columns == (
        "鏈別",
        "Capability",
        "Provider",
        "取得筆數",
        "完整度",
        "截斷",
        "截斷原因",
        "警告",
    )
    assert "private_cursor" not in str(table.rows)


def test_dust_and_spam_candidate_move_to_appendix():
    document = ReportComposer().compose(
        analysis(), materiality_thresholds={"DUST": Decimal("1")}
    )
    assert {row[0] for row in section(document, "asset_flows").tables[0].rows} == {
        "USDT"
    }
    appendix = section(document, "non_material_assets").tables[0]
    assert appendix.rows[0][0] == "DUST"
    assert appendix.rows[0][4] == "spam candidate"


def test_user_can_include_or_exclude_assets():
    included = ReportComposer().compose(
        analysis(),
        materiality_thresholds={"DUST": Decimal("1")},
        include_assets=frozenset({"DUST"}),
    )
    excluded = ReportComposer().compose(
        analysis(), exclude_assets=frozenset({"USDT"})
    )
    assert "DUST" in {
        row[0] for row in section(included, "asset_flows").tables[0].rows
    }
    assert "USDT" in {
        row[0]
        for row in section(excluded, "non_material_assets").tables[0].rows
    }


def test_candidate_role_is_not_confirmed_payment():
    document = ReportComposer().compose(
        analysis(), investigation=investigation()
    )
    rows = section(document, "outgoing_distribution").tables[0].rows
    assert all("payment" not in row[3] for row in rows)


def test_evidence_index_deduplicates_artifact_and_preserves_hash():
    artifact = ReportEvidence(
        "E1",
        "investigation",
        "investigation_evidence.json",
        "investigation_evidence.json",
        "artifact",
        hash="a" * 64,
    )
    document = ReportComposer().compose(
        analysis(),
        investigation=investigation(),
        evidence=(artifact, artifact),
    )
    assert len(document.evidence) == 1
    assert document.evidence[0].hash == "a" * 64
    assert "IF0" in document.evidence[0].metadata["record_ids"]


def test_hash_unavailable_is_limitation_not_verified():
    document = ReportComposer().compose(
        analysis(), investigation=investigation()
    )
    evidence_text = " ".join(section(document, "evidence_index").content_blocks)
    assert "hash unavailable" in evidence_text
    assert "verified" not in evidence_text
    assert any(
        item.code == "evidence_hash_unavailable"
        for item in document.limitations
    )


def test_conclusion_fact_layers_are_distinct_sections():
    document = ReportComposer().compose(
        analysis(), investigation=investigation()
    )
    ids = {item.section_id for item in document.sections}
    assert {
        "confirmed_facts",
        "investigation_facts",
        "candidate_interpretations",
        "unresolved_questions",
        "recommended_follow_up",
        "limitations",
    }.issubset(ids)


def test_main_report_does_not_render_python_dict_repr():
    document = ReportComposer().compose(
        analysis(), investigation=investigation()
    )
    rendered = " ".join(
        cell
        for item in document.sections
        for table in item.tables
        for row in table.rows
        for cell in row
    )
    assert "{'" not in rendered


def test_metadata_records_all_pipeline_counts():
    document = ReportComposer().compose(
        analysis(), graph=graph(), investigation=investigation()
    )
    assert document.metadata.provider_raw_record_count == 1200
    assert document.metadata.normalized_record_count == 1000
    assert document.metadata.analysis_record_count == 1000
    assert document.metadata.investigation_edge_count == 808
    assert document.metadata.graph_edge_count == 808
    assert document.metadata.rejected_count == 20
    assert document.metadata.deduplicated_count == 168
    assert document.metadata.failed_count == 4
    assert document.metadata.unclassified_count == 8
    assert document.metadata.excluded_by_scope == 12
