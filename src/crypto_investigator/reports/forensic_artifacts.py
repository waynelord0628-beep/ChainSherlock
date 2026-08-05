import ast
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from crypto_investigator.reports.models import ReportDocument


_PROMOTIONAL_AMOUNTS = {
    Decimal("8888.88"),
    Decimal("4444.44"),
    Decimal("888.88"),
    Decimal("888.80"),
    Decimal("888.00"),
    Decimal("1000.00"),
}


def _table(document: ReportDocument, table_id: str):
    return next(
        (
            table
            for section in document.sections
            for table in section.tables
            if table.table_id == table_id
        ),
        None,
    )


def suspicious_trx_candidates(document: ReportDocument) -> tuple[dict, ...]:
    """Create reversible aggregate candidates when tx-level artifacts are absent."""
    funding = _table(document, "funding_sources")
    rows = [
        row
        for row in (funding.rows if funding else ())
        if len(row) >= 7 and str(row[1]).upper() == "TRX"
    ]
    grouped = {}
    for row in rows:
        try:
            normalized = Decimal(str(row[3])).quantize(Decimal("0.01"))
        except InvalidOperation:
            continue
        grouped.setdefault(normalized, []).append(row)
    candidates = []
    for amount, same_amount_rows in sorted(grouped.items(), reverse=True):
        if amount not in _PROMOTIONAL_AMOUNTS or len(same_amount_rows) < 2:
            continue
        for row in same_amount_rows:
            candidates.append(
                {
                    "txid": "unavailable_in_aggregate_artifact",
                    "block": None,
                    "timestamp": str(row[5]),
                    "sender": str(row[2]),
                    "receiver": document.metadata.target_address,
                    "contract_type": "unavailable_in_aggregate_artifact",
                    "raw_amount": str(row[3]),
                    "normalized_amount": str(amount),
                    "result_status": "unavailable_in_aggregate_artifact",
                    "memo_or_data": None,
                    "sender_outbound_recipient_count": None,
                    "same_amount_recipient_count": None,
                    "same_amount_source_count": len(same_amount_rows),
                    "same_amount_frequency": len(same_amount_rows),
                    "external_label_status": "not_available",
                    "classification": "promotional_candidate",
                    "reason_codes": [
                        "salient_fixed_amount",
                        "same_amount_multiple_sources",
                    ],
                    "confidence": "medium",
                    "source_evidence": ["funding_sources"],
                    "human_review_status": "not_reviewed",
                    "included_in_fund_flow": False,
                    "reversible": True,
                    "limitation": (
                        "正式 artifact 僅保存彙總列；txid、fan-out、memo 與 contract "
                        "metadata 無法離線還原，候選仍待人工覆核。"
                    ),
                }
            )
    return tuple(candidates)


def trx_reconciliation(document: ReportDocument) -> dict:
    asset_flows = _table(document, "asset_flows")
    trx = next(
        (
            row
            for row in (asset_flows.rows if asset_flows else ())
            if str(row[0]).upper() == "TRX"
        ),
        None,
    )
    def amount(value) -> Decimal:
        try:
            return Decimal(str(value).replace(",", ""))
        except InvalidOperation:
            return Decimal(0)

    gross_inflow = amount(trx[1]) if trx else Decimal(0)
    gross_outflow = amount(trx[2]) if trx else Decimal(0)
    candidates = suspicious_trx_candidates(document)
    quarantined = sum(
        (Decimal(item["normalized_amount"]) for item in candidates),
        Decimal(0),
    )
    material = gross_inflow - quarantined
    return {
        "schema_version": 1,
        "basis": "aggregate_funding_rows",
        "gross_on_chain_inflow": str(gross_inflow),
        "gross_on_chain_outflow": str(gross_outflow),
        "normal_value_transfer": "unavailable_without_tx_level_artifact",
        "promotional_candidate": str(quarantined),
        "dusting_candidate": "0",
        "phishing_candidate": "0",
        "resource_or_system_excluded": "unavailable_without_tx_level_artifact",
        "failed_excluded": "unavailable_without_tx_level_artifact",
        "final_material_inflow": str(material),
        "candidate_count": len(candidates),
        "human_review_status": "not_reviewed",
        "external_baseline": {
            "inflow": "5243.1171",
            "outflow": "4581.5177",
            "usage": "comparison_only",
        },
        "limitations": [
            "外部 baseline 僅供比較，未用於覆寫計算。",
            "正式 6,935 筆 artifact 未保存逐筆 TRON contract、memo、fan-out 與 txid。",
            "Material inflow 為可逆候選隔離結果，尚未經人工確認。",
        ],
    }


def fixed_amount_rows(document: ReportDocument) -> tuple[tuple[str, int, str, str, str, str], ...]:
    patterns = _table(document, "transfer_patterns")
    values = {
        str(row[0]): str(row[1])
        for row in (patterns.rows if patterns else ())
        if len(row) >= 2
    }
    raw = values.get("fixed_amounts")
    parsed = {}
    if raw:
        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            parsed = {}
    if not parsed:
        text = values.get("主要固定金額", "")
        for group in text.split("；"):
            if "：" not in group:
                continue
            asset, amounts = group.split("：", 1)
            parsed[asset] = [item for item in amounts.split("、") if item]
    rows = []
    for asset, amounts in sorted(parsed.items()):
        for rank, amount in enumerate(amounts[:8], 1):
            rows.append(
                (
                    str(asset),
                    rank,
                    str(amount),
                    "未保存",
                    "未保存",
                    f"OBS-FIXED-{str(asset).upper()}-{rank:03d}",
                )
            )
    return tuple(rows)


def claim_mapping(document: ReportDocument) -> dict:
    evidence = [
        {
            "artifact_id": item.evidence_id,
            "source": item.source,
            "sha256": item.hash,
        }
        for item in document.evidence
    ]
    ids = (
        "FACT-SCOPE-001",
        "FACT-COUNT-001",
        "FACT-ASSET-USDT-001",
        "FACT-ASSET-TRX-001",
        "FACT-PROVIDER-001",
        "FACT-GRAPH-001",
        "OBS-FUNDING-USDT-001",
        "OBS-FUNDING-USDT-002",
        "OBS-FUNDING-TRX-001",
        "OBS-BATCH-IN-001",
        "OBS-BATCH-OUT-001",
        "OBS-FIXED-USDT-001",
        "OBS-FIXED-TRX-001",
        "OBS-DORMANCY-001",
        "OBS-STAGE-001",
        "CAND-SERVICE-001",
        "CAND-FLOW-USDT-001",
        "CAND-FLOW-TRX-001",
    )
    return {
        "schema_version": 1,
        "claims": [
            {
                "claim_id": claim_id,
                "source_records": [],
                "artifacts": evidence,
                "limitation": (
                    "目前正式 ReportDocument 僅保存 artifact-level mapping；"
                    "逐筆 source record mapping 不可用。"
                ),
            }
            for claim_id in ids
        ],
    }


def write_forensic_artifacts(document: ReportDocument, root: Path) -> dict[str, str]:
    fixed_path = root / "fixed_amounts.csv"
    with fixed_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("資產", "排名", "固定金額", "出現次數", "占比", "Observation ID"))
        writer.writerows(fixed_amount_rows(document))

    suspicious_path = root / "suspicious_trx_transfers.csv"
    candidates = suspicious_trx_candidates(document)
    columns = (
        "txid", "block", "timestamp", "sender", "receiver", "contract_type",
        "raw_amount", "normalized_amount", "result_status", "memo_or_data",
        "sender_outbound_recipient_count", "same_amount_recipient_count",
        "same_amount_source_count", "same_amount_frequency",
        "external_label_status", "classification", "reason_codes", "confidence",
        "source_evidence", "human_review_status", "included_in_fund_flow",
        "reversible", "limitation",
    )
    with suspicious_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for item in candidates:
            writer.writerow(
                {
                    **item,
                    "reason_codes": "|".join(item["reason_codes"]),
                    "source_evidence": "|".join(item["source_evidence"]),
                }
            )

    reconciliation_path = root / "trx_reconciliation.json"
    reconciliation_path.write_text(
        json.dumps(trx_reconciliation(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    mapping_path = root / "claim_mapping.json"
    mapping_path.write_text(
        json.dumps(claim_mapping(document), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "fixed_amounts": fixed_path.name,
        "suspicious_trx_transfers": suspicious_path.name,
        "trx_reconciliation": reconciliation_path.name,
        "claim_mapping": mapping_path.name,
    }
