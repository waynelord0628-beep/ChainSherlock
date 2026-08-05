from __future__ import annotations

HUMAN_LABELS = {
    "identify_main_sources": "找出主要資金來源",
    "identify_main_destinations": "找出主要資金去向",
    "detect_batch_distribution": "辨識批次出款模式",
    "detect_funding_transition": "辨識供款來源變化",
    "identify_service_candidates": "辨識可能服務商",
    "generate_investigation_report": "產生案件調查報告",
    "validate_case_inputs": "確認案件資料",
    "parse_structured_attachment": "讀取結構化附件",
    "import_transactions": "匯入交易資料",
    "detect_chain": "辨識區塊鏈網路",
    "analyze_address": "分析地址交易",
    "analyze_transaction": "分析指定交易",
    "compare_known_addresses": "比較已知地址",
    "match_victim_transactions": "核對指定交易",
    "build_graph": "建立資金流向圖",
    "trace_funds": "多層資金追蹤",
    "run_investigation_features": "整理調查觀察",
    "apply_local_labels": "套用本機標籤",
    "generate_narrative": "整理案件敘事",
    "generate_report": "產生案件報告",
    "export_evidence_manifest": "建立證據清冊",
    "request_manual_review": "等待人工覆核",
    "unsupported_recommended_step": "建議的外部調查步驟",
}


def human_label(value: object) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "")
    return HUMAN_LABELS.get(text, text.replace("_", " ").strip().title() or "未提供")
