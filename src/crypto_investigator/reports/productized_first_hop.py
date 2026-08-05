from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping

from crypto_investigator.reports.formatting import abbreviate_identifier
from crypto_investigator.reports.models import ReportDocument, ReportSection, ReportTable


def _decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _amount(value, asset: str | None = None) -> str:
    number = _decimal(value).quantize(Decimal("0.01"))
    suffix = f" {asset}" if asset else ""
    return f"{number:,.2f}{suffix}"


def _percent(value) -> str:
    return f"{_decimal(value) * Decimal('100'):.2f}%"


def _address_ref(address: str, registry: Mapping[str, str], *, full=False) -> str:
    display_id = registry.get(address, "地址-未編號")
    if full:
        return f"{address}（{display_id}）"
    return f"{display_id}\n{abbreviate_identifier(address)}"


def _principal(document: ReportDocument) -> Mapping:
    product = document.metadata.first_hop_product or {}
    return product.get("principal_asset") or {}


def _top_counterparty(principal: Mapping, side: str) -> Mapping:
    rows = principal.get(side) or ()
    return rows[0] if rows else {}


def _executive_summary(document: ReportDocument, registry) -> ReportSection:
    principal = _principal(document)
    asset = str(principal.get("asset") or "主要價值資產")
    source = _top_counterparty(principal, "sources")
    destination = _top_counterparty(principal, "destinations")
    target = str(document.metadata.target_address or "未提供")
    content = [
        (
            f"本報告針對 {target} 執行地址剖繪與第一層資金流分析。"
            "分析結果僅反映目前完整取得的鏈上資料，不代表已完成第二層追蹤、"
            "下車點確認或地址身分認定。"
        ),
        (
            f"主要價值資產為 {asset}；共納入 "
            f"{int(principal.get('material_transaction_count', 0)):,} 筆重要交易，"
            f"流入 {_amount(principal.get('incoming_total', 0), asset)}，"
            f"流出 {_amount(principal.get('outgoing_total', 0), asset)}，"
            f"淨流量 {_amount(principal.get('net_flow', 0), asset)}。"
        ),
    ]
    if source:
        content.append(
            f"最大資金來源為 {_address_ref(str(source['address']), registry)}，"
            f"累計 {_amount(source.get('amount', 0), asset)}，"
            f"占主要資產流入 {_percent(source.get('share', 0))}。"
        )
    if destination:
        content.append(
            f"最大第一層去向為 {_address_ref(str(destination['address']), registry)}，"
            f"累計 {_amount(destination.get('amount', 0), asset)}，"
            f"占主要資產流出 {_percent(destination.get('share', 0))}。"
        )
    content.append(
        "第一層來源與去向係分別依鏈上收付紀錄排名；兩者並列不代表同一筆資金"
        "已完成逐筆路徑追蹤。"
    )
    return ReportSection(
        "product_executive_summary",
        "執行摘要",
        10,
        tuple(content),
    )


def _completeness(document: ReportDocument) -> ReportSection:
    metadata = document.metadata
    product = metadata.first_hop_product or {}
    principal = product.get("principal_asset") or {}
    return ReportSection(
        "product_completeness",
        "資料完整度與分析邊界",
        31,
        (
            "資料取得完整度、資產分類完整度與本報告實際分析母體分開揭露；"
            "技術欄位與原始資產識別碼保留於 report_data.json。",
        ),
        tables=(
            ReportTable(
                "product_completeness",
                "本次分析範圍",
                ("項目", "結果", "說明"),
                (
                    (
                        "鏈上資料取得",
                        "完整" if metadata.full_history_complete else "部分",
                        f"完整取得 {metadata.provider_raw_record_count:,} 筆 Provider 紀錄",
                    ),
                    (
                        "正規化交易",
                        f"{metadata.normalized_record_count:,} 筆",
                        "保留於結構化 artifact",
                    ),
                    (
                        "主要價值資產",
                        str(principal.get("asset") or "尚未確認"),
                        "依重要性與可支配價值規則判定",
                    ),
                    (
                        "主要分析母體",
                        f"{int(principal.get('material_transaction_count', 0)):,} 筆",
                        "排除零值、微額與非主要價值資產紀錄",
                    ),
                    (
                        "第一層資金流",
                        "已完成",
                        "尚未展開主要去向的下一層交易",
                    ),
                    (
                        "下車點識別",
                        "尚未執行",
                        "不得據此確認最終受益人或服務商",
                    ),
                    (
                        "Graph",
                        "完整" if metadata.graph_completeness == "complete" else "部分",
                        "Graph 狀態與 flow_graph artifact 一致",
                    ),
                ),
            ),
        ),
    )


def _asset_facts(document: ReportDocument) -> ReportSection:
    product = document.metadata.first_hop_product or {}
    assets = product.get("assets") or ()
    rows = []
    for item in assets:
        asset = str(item.get("asset") or "未命名資產")
        if asset not in {"USDT", "TRX"}:
            continue
        role = str(item.get("role") or "")
        if asset == "USDT":
            role_label = "主要價值資產"
        elif asset == "TRX":
            role_label = "營運／手續費資產"
        elif role == "secondary_value_asset":
            role_label = "次要價值資產"
        else:
            continue
        rows.append(
            (
                f"FACT-ASSET-{asset.upper()}-001",
                asset,
                role_label,
                f"{int(item.get('material_transaction_count', 0)):,}",
                _amount(item.get("incoming_total", 0), asset),
                _amount(item.get("outgoing_total", 0), asset),
            )
        )
    return ReportSection(
        "product_asset_facts",
        "主要資產與角色",
        41,
        (
            "USDT 與 TRX 依案件用途分開呈現；TRC10、Spam 候選與未知資產"
            "不參與主要價值資產排名。",
        ),
        tables=(
            ReportTable(
                "product_asset_facts",
                "資產角色摘要",
                ("Fact ID", "資產", "本案角色", "重要交易數", "流入", "流出"),
                tuple(rows),
            ),
        ),
    )


def _principal_structure(document: ReportDocument) -> ReportSection:
    principal = _principal(document)
    asset = str(principal.get("asset") or "主要價值資產")
    source_share = principal.get("source_concentration") or {}
    destination_share = principal.get("destination_concentration") or {}
    rows = (
        ("重要交易數", f"{int(principal.get('material_transaction_count', 0)):,} 筆"),
        ("流入筆數", f"{int(principal.get('incoming_count', 0)):,} 筆"),
        ("流出筆數", f"{int(principal.get('outgoing_count', 0)):,} 筆"),
        ("流入總額", _amount(principal.get("incoming_total", 0), asset)),
        ("流出總額", _amount(principal.get("outgoing_total", 0), asset)),
        ("雙向交易總量", _amount(principal.get("bidirectional_volume", 0), asset)),
        ("淨流量", _amount(principal.get("net_flow", 0), asset)),
        ("主要交易對手數", f"{int(principal.get('total_nonzero_counterparties', 0)):,}"),
        (
            "來源集中度",
            "第一名 "
            f"{_percent(source_share.get('top_1_share', 0))}；"
            "前五名 "
            f"{_percent(source_share.get('top_5_share', 0))}；"
            "前十名 "
            f"{_percent(source_share.get('top_10_share', 0))}",
        ),
        (
            "去向集中度",
            "第一名 "
            f"{_percent(destination_share.get('top_1_share', 0))}；"
            "前五名 "
            f"{_percent(destination_share.get('top_5_share', 0))}；"
            "前十名 "
            f"{_percent(destination_share.get('top_10_share', 0))}",
        ),
    )
    return ReportSection(
        "benchmark_usdt_structure",
        f"{asset} 整體資金結構",
        49,
        (
            f"{asset} 為本案主要價值資產；本節金額統一四捨五入至小數點後兩位，"
            "原始 Decimal 精度仍保留於 report_data.json。",
        ),
        tables=(
            ReportTable(
                "benchmark_usdt_summary",
                f"{asset} 資產摘要",
                ("項目", "結果"),
                rows,
            ),
        ),
    )


def _candidate_sections(document: ReportDocument, registry) -> tuple[ReportSection, ...]:
    product = document.metadata.first_hop_product or {}
    candidates = product.get("first_hop_candidates") or ()
    tables = []
    for index, item in enumerate(candidates[:3], 1):
        asset = str(item.get("asset") or "資產未保存")
        address = str(item.get("address") or "")
        evidence_refs = tuple(str(value) for value in item.get("evidence_refs", ()))
        tables.append(
            ReportTable(
                f"first_hop_candidate_{index}",
                f"優先候選 {index}｜{_address_ref(address, registry)}",
                ("調查項目", "目前結果"),
                (
                    ("完整地址", _address_ref(address, registry, full=True)),
                    ("資產", asset),
                    ("收受金額", _amount(item.get("received_amount", 0), asset)),
                    ("占目標地址流出", _percent(item.get("share_of_target_outflow", 0))),
                    ("交易次數", f"{int(item.get('transaction_count', 0)):,}"),
                    (
                        "重要性",
                        "依收受金額及流出占比列為下一層優先查證地址",
                    ),
                    (
                        "目前可確認",
                        "可確認目標地址曾向該地址執行第一層轉出",
                    ),
                    (
                        "尚待查證",
                        "後續去向、地址身分、Local Label 與是否進入 VASP",
                    ),
                    (
                        "建議行動",
                        "取得該地址同資產完整交易並進行第二層追蹤",
                    ),
                    (
                        "Evidence",
                        f"{item.get('candidate_id', f'FH-{index:03d}')}"
                        + (f"；來源交易 {len(evidence_refs):,} 筆" if evidence_refs else ""),
                    ),
                    (
                        "限制",
                        "候選不等同已確認下車點，亦不代表地址身分已獲確認",
                    ),
                ),
            )
        )
    if not tables:
        return ()
    return (
        ReportSection(
            "first_hop_candidates",
            "主要價值資產第一層去向候選",
            55,
            (
                "以下候選均由真實第一層轉出交易支持，依收受金額與占比排序；"
                "本報告未將來源排行與去向排行拼接成確定資金路徑。",
            ),
            tables=tuple(tables),
        ),
    )


def _insights(document: ReportDocument, registry) -> ReportSection:
    principal = _principal(document)
    asset = str(principal.get("asset") or "主要價值資產")
    source = _top_counterparty(principal, "sources")
    destination = _top_counterparty(principal, "destinations")
    net = _decimal(principal.get("net_flow", 0))
    inflow = _decimal(principal.get("incoming_total", 0))
    retention = net / inflow if inflow else Decimal("0")
    rows = []
    if source:
        rows.append(
            (
                "OBS-FUNDING-001",
                f"最大來源 {_address_ref(str(source['address']), registry)} "
                f"占 {asset} 流入 {_percent(source.get('share', 0))}。",
                "來源集中度",
                "目前只能確認鏈上供款關係，不能推定控制權",
            )
        )
    if destination:
        rows.append(
            (
                "OBS-OUTFLOW-001",
                f"最大第一層去向 {_address_ref(str(destination['address']), registry)} "
                f"占 {asset} 流出 {_percent(destination.get('share', 0))}。",
                "去向集中度",
                "尚未取得該地址下一層完整交易",
            )
        )
    rows.append(
        (
            "OBS-NET-001",
            f"{asset} 淨流量為 {_amount(net, asset)}，約占總流入 "
            f"{_percent(retention)}。",
            "收付規模接近",
            "不等同逐筆快速轉出或 FIFO 路徑證明",
        )
    )
    return ReportSection(
        "deterministic_insights",
        "規則式調查洞察",
        90,
        (
            "以下內容由相同 structured data 依固定規則產生，不使用 AI，"
            "不新增地址、金額、Label 或身分判斷。",
        ),
        tables=(
            ReportTable(
                "deterministic_insights",
                "主要調查發現",
                ("Observation ID", "觀察", "調查意義", "限制"),
                tuple(rows),
            ),
        ),
    )


def _technical_exclusions(document: ReportDocument) -> ReportSection:
    product = document.metadata.first_hop_product or {}
    excluded = sum(
        int(item.get("excluded_count", 0))
        for item in product.get("assets", ())
    )
    return ReportSection(
        "technical_exclusions",
        "技術性排除摘要",
        209,
        (
            f"另有 {excluded:,} 筆低於重要性門檻、TRC10、Spam 候選或未知資產"
            "紀錄保留於原始 Evidence 與技術 artifact，未納入主要資金流、"
            "階段、停留時間或規則式洞察。詳細資料請參閱 "
            "technical_exclusions.json、non_material_assets.csv 與 report_data.json。",
        ),
    )


def build_productized_sections(
    document: ReportDocument,
    registry: Mapping[str, str],
) -> tuple[ReportSection, ...]:
    if not document.metadata.first_hop_product:
        return ()
    return (
        _executive_summary(document, registry),
        _completeness(document),
        _asset_facts(document),
        _principal_structure(document),
        *_candidate_sections(document, registry),
        _insights(document, registry),
        _technical_exclusions(document),
    )


def normalize_address_registry(
    section: ReportSection,
    document: ReportDocument,
) -> ReportSection:
    """Keep the front registry compact; complete technical mapping remains in CSV."""
    product = document.metadata.first_hop_product or {}
    roles: dict[str, list[str]] = {}
    assets: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    target = str(document.metadata.target_address or "")
    if target:
        roles[target] = ["調查標的"]
    for analysis in product.get("assets", ()):
        asset = str(analysis.get("asset") or "")
        if asset not in {"USDT", "TRX"}:
            continue
        for side, role in (
            ("sources", f"{asset} 主要來源"),
            ("destinations", f"{asset} 主要去向"),
        ):
            for item in analysis.get(side, ()):
                address = str(item.get("address") or "")
                roles.setdefault(address, [])
                if role not in roles[address]:
                    roles[address].append(role)
                assets.setdefault(address, set()).add(asset)
                if item.get("label"):
                    labels[address] = str(item["label"])
    for item in product.get("first_hop_candidates", ()):
        address = str(item.get("address") or "")
        roles.setdefault(address, [])
        if "後續追蹤優先" not in roles[address]:
            roles[address].append("後續追蹤優先")
        assets.setdefault(address, set()).add(str(item.get("asset") or ""))

    tables = []
    for table in section.tables:
        if table.table_id != "address_registry_identity":
            continue
        rows = []
        for row in table.rows:
            address = str(row[2]) if len(row) >= 3 else ""
            role = "／".join(roles.get(address, ("其他主文引用地址",))[:2])
            asset = "／".join(sorted(value for value in assets.get(address, ()) if value))
            label = labels.get(address) or (str(row[3]) if len(row) >= 4 else "未標記")
            if len(row) >= 7:
                rows.append((row[0], address, row[1], role, asset or "未分類", label))
            elif len(row) >= 4:
                rows.append((row[0], address, row[1], role, asset or "未分類", label))
        tables.append(
            ReportTable(
                table.table_id,
                "完整地址索引",
                ("地址編號", "完整地址", "鏈別", "主要角色", "主要資產", "Label"),
                tuple(rows),
            )
        )
    return replace_section(
        section,
        title="本報告地址索引",
        content_blocks=(
            "下列完整地址供正文查核與複製；地址編號僅為固定引用索引，"
            "不代表資金排名。完整 Evidence mapping 另存於 address_registry.csv。",
        ),
        tables=tuple(tables),
    )


def replace_section(section: ReportSection, **changes) -> ReportSection:
    values = {
        "section_id": section.section_id,
        "title": section.title,
        "order": section.order,
        "content_blocks": section.content_blocks,
        "tables": section.tables,
        "figures": section.figures,
        "evidence_refs": section.evidence_refs,
        "warnings": section.warnings,
        "limitations": section.limitations,
        "section_type": section.section_type,
        "claims": section.claims,
        "fact_refs": section.fact_refs,
        "observation_refs": section.observation_refs,
        "confidence": section.confidence,
        "review_status": section.review_status,
    }
    values.update(changes)
    return ReportSection(**values)
