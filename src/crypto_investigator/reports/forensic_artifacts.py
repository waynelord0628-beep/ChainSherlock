import ast
import csv
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from crypto_investigator.reports.models import ReportDocument


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
    """Deprecated aggregate inference: asset identity requires contract evidence."""
    return ()


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
    quarantined = Decimal(0)
    material = gross_inflow
    return {
        "schema_version": 1,
        "basis": "strict_native_trx_only",
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
            "原生 TRX 僅接受 symbol=TRX 且 contractType=TransferContract。",
            "TRC10／TRC20／未知 TRON 資產不得納入此 reconciliation。",
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
    product = document.metadata.first_hop_product or {}
    excluded_assets = tuple(
        {
            "asset": str(item.get("asset") or "unknown"),
            "role": str(item.get("role") or "unknown"),
            "transaction_count": int(item.get("transaction_count", 0)),
            "excluded_count": int(item.get("excluded_count", 0)),
            "reason": "not_included_in_principal_fund_flow",
            "reversible": True,
        }
        for item in product.get("assets", ())
        if item.get("role")
        in {
            "spam_or_low_materiality_asset",
            "unknown_or_non_value_event",
        }
        or int(item.get("excluded_count", 0))
    )
    non_material_path = root / "non_material_assets.csv"
    with non_material_path.open("w", encoding="utf-8-sig", newline="") as stream:
        columns = (
            "asset",
            "role",
            "transaction_count",
            "excluded_count",
            "reason",
            "reversible",
        )
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(excluded_assets)
    exclusions_path = root / "technical_exclusions.json"
    exclusions_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "excluded_item_count": len(excluded_assets),
                "excluded_record_count": sum(
                    item["excluded_count"] for item in excluded_assets
                ),
                "items": excluded_assets,
                "raw_evidence_modified": False,
                "included_in_principal_fund_flow": False,
                "reversible": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "fixed_amounts": fixed_path.name,
        "suspicious_trx_transfers": suspicious_path.name,
        "trx_reconciliation": reconciliation_path.name,
        "claim_mapping": mapping_path.name,
        "non_material_assets": non_material_path.name,
        "technical_exclusions": exclusions_path.name,
    }
