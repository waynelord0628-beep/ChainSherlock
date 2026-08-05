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


def _bar(value, maximum, width: int = 18) -> str:
    current = _decimal(value)
    ceiling = _decimal(maximum)
    if current <= 0 or ceiling <= 0:
        return ""
    filled = max(1, min(width, int((current / ceiling) * width)))
    return "|" * filled


def _address_ref(address: str, registry: Mapping[str, str], *, full=False) -> str:
    if address not in registry:
        raise ValueError("Address registry snapshot is incomplete")
    display_id = registry[address]
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
            f"主要價值資產為 {asset}；共取得 "
            f"{int(principal.get('transaction_count', 0)):,} 筆 {asset} 紀錄，"
            f"其中 {int(principal.get('material_transaction_count', 0)):,} 筆為"
            f"非零資金移轉，另有 {int(principal.get('zero_value_count', 0)):,} 筆"
            "零值合約互動。"
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
        ("USDT 總紀錄", f"{int(principal.get('transaction_count', 0)):,} 筆"),
        (
            "非零資金移轉",
            f"{int(principal.get('material_transaction_count', 0)):,} 筆",
        ),
        ("零值合約互動", f"{int(principal.get('zero_value_count', 0)):,} 筆"),
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


def _chart_sections(
    document: ReportDocument,
    registry: Mapping[str, str],
) -> tuple[ReportSection, ...]:
    principal = _principal(document)
    asset = str(principal.get("asset") or "USDT")
    sources = tuple(principal.get("sources") or ())[:5]
    destinations = tuple(principal.get("destinations") or ())[:5]

    flow_rows = []
    for index in range(max(len(sources), len(destinations))):
        source = sources[index] if index < len(sources) else {}
        destination = destinations[index] if index < len(destinations) else {}
        flow_rows.append(
            (
                (
                    f"{_address_ref(str(source['address']), registry)}\n"
                    f"{_amount(source.get('amount', 0), asset)}"
                    if source
                    else ""
                ),
                f"{asset}\n調查標的",
                (
                    f"{_address_ref(str(destination['address']), registry)}\n"
                    f"{_amount(destination.get('amount', 0), asset)}"
                    if destination
                    else ""
                ),
            )
        )

    monthly = tuple(principal.get("monthly") or ())
    monthly_max = max(
        (
            max(_decimal(item.get("incoming", 0)), _decimal(item.get("outgoing", 0)))
            for item in monthly
        ),
        default=Decimal("0"),
    )
    monthly_rows = tuple(
        (
            str(item.get("period") or ""),
            _bar(item.get("incoming", 0), monthly_max),
            _amount(item.get("incoming", 0)),
            _bar(item.get("outgoing", 0), monthly_max),
            _amount(item.get("outgoing", 0)),
        )
        for item in monthly
    )

    destination_max = max(
        (_decimal(item.get("amount", 0)) for item in destinations),
        default=Decimal("0"),
    )
    destination_rows = tuple(
        (
            str(index),
            _address_ref(str(item.get("address") or ""), registry),
            _bar(item.get("amount", 0), destination_max),
            _amount(item.get("amount", 0), asset),
            _percent(item.get("share", 0)),
        )
        for index, item in enumerate(destinations, 1)
    )

    return (
        ReportSection(
            "deterministic_flow_chart",
            "USDT 第一層資金流向圖",
            52,
            (
                "本圖分別呈現前五大來源與前五大去向；左右兩側為獨立規則式排名，"
                "不代表同一筆資金已完成路徑級追蹤。",
            ),
            tables=(
                ReportTable(
                    "deterministic_flow_chart",
                    "前五大來源 → 調查標的 → 前五大去向",
                    ("主要來源", "調查標的", "主要去向"),
                    tuple(flow_rows),
                ),
            ),
        ),
        ReportSection(
            "deterministic_monthly_chart",
            "USDT 月度流入／流出圖",
            53,
            (
                "橫條依全期間單月最大值等比例繪製；金額以 USDT 表示，"
                "原始 Decimal 精度仍保留於 report_data.json。",
            ),
            tables=(
                ReportTable(
                    "deterministic_monthly_chart",
                    "月度資金活動",
                    ("月份", "流入強度", "流入金額", "流出強度", "流出金額"),
                    monthly_rows,
                ),
            ),
        ),
        ReportSection(
            "deterministic_destination_chart",
            "USDT 前五大去向金額圖",
            54,
            tables=(
                ReportTable(
                    "deterministic_destination_chart",
                    "第一層去向金額與占比",
                    ("排名", "地址參照", "相對金額", "流出金額", "占比"),
                    destination_rows,
                ),
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
            f"{asset} 淨流量為 {_amount(net, asset)}；以「淨流量 ÷ "
            f"{asset} 流入總額」計算，占流入總額 {_percent(retention)}。",
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
    assets = tuple(product.get("assets", ()))
    principal = _principal(document)
    zero_value = int(principal.get("zero_value_count", 0))
    non_core = sum(
        int(item.get("transaction_count", 0))
        for item in assets
        if item.get("asset") not in {"USDT", "TRX"}
    )
    micro_native = int(document.metadata.micro_excluded_count)
    unclassified = int(document.metadata.unclassified_count)
    return ReportSection(
        "technical_exclusions",
        "技術性排除摘要",
        209,
        (
            "下列項目保留於原始 Evidence 與技術 artifact，但不納入主要資金流、"
            "地址角色或規則式洞察。各類別可能屬不同統計層級，不應直接相加；"
            "排除結果可逆，詳細欄位保存於 "
            "technical_exclusions.json、non_material_assets.csv 與 report_data.json。",
        ),
        tables=(
            ReportTable(
                "technical_exclusion_summary",
                "技術性排除摘要",
                ("類別", "筆數", "處理方式", "可逆"),
                (
                    ("USDT 零值合約互動", f"{zero_value:,}", "保留紀錄，不計金額", "是"),
                    ("低重要性／非核心資產", f"{non_core:,}", "移至技術附件", "是"),
                    ("微額原生資產", f"{micro_native:,}", "排除主要行為分析", "是"),
                    ("未分類技術事件", f"{unclassified:,}", "保留待查", "是"),
                ),
            ),
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
        *_chart_sections(document, registry),
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
    identity: dict[str, tuple[str, str]] = {}
    for table in section.tables:
        if table.table_id == "address_registry_identity":
            for row in table.rows:
                if len(row) >= 3:
                    identity[str(row[2])] = (str(row[0]), str(row[1]))

    activities: dict[str, list[dict]] = {}
    target = str(document.metadata.target_address or "")
    for analysis in product.get("assets", ()):
        asset = str(analysis.get("asset") or "")
        if asset not in {"USDT", "TRX"}:
            continue
        for side, direction in (
            ("sources", "來源"),
            ("destinations", "去向"),
        ):
            for item in analysis.get(side, ()):
                address = str(item.get("address") or "")
                activities.setdefault(address, []).append(
                    {
                        "asset": asset,
                        "direction": direction,
                        "amount": _decimal(item.get("amount", 0)),
                        "rank": int(item.get("rank", 999)),
                    }
                )

    candidate_addresses = {
        str(item.get("address") or "")
        for item in product.get("first_hop_candidates", ())
    }
    addresses = set(activities)
    if target:
        addresses.add(target)

    rows = []
    amount_by_address = {}
    for address in addresses:
        if address not in identity:
            raise ValueError("Address registry snapshot is incomplete")
        display_id, _chain = identity[address]
        if address == target:
            rows.append(("調查標的", f"{address}（{display_id}）", "—", "—", "高"))
            amount_by_address[address] = Decimal("0")
            continue
        ranked = sorted(
            activities.get(address, ()),
            key=lambda item: (-item["amount"], item["asset"], item["direction"]),
        )
        primary = ranked[0]
        secondary = []
        for item in ranked[1:]:
            label = f"{item['asset']} {item['direction']}活動"
            if label not in secondary:
                secondary.append(label)
        if address in candidate_addresses:
            secondary.append("後續追蹤候選")
        role = f"主要：{primary['asset']} 主要{primary['direction']}"
        if secondary:
            role += "\n次要：" + "、".join(secondary[:2])
        asset_lines = []
        for item in ranked:
            if item["asset"] not in asset_lines:
                asset_lines.append(item["asset"])
        amount_lines = [
            f"{item['direction']} {_amount(item['amount'], item['asset'])}"
            for item in ranked[:2]
        ]
        priority = "高" if address in candidate_addresses or primary["rank"] == 1 else "中"
        rows.append(
            (
                role,
                f"{address}（{display_id}）",
                "\n".join(asset_lines),
                "\n".join(amount_lines),
                priority,
            )
        )
        amount_by_address[address] = max(item["amount"] for item in ranked)

    def sort_key(row):
        if row[0] == "調查標的":
            return (0, 0, Decimal("0"), row[1])
        address = next(
            (value for value in amount_by_address if value in row[1]),
            "",
        )
        return (
            1,
            0 if row[4] == "高" else 1,
            -amount_by_address.get(address, Decimal("0")),
            row[1],
        )

    rows = sorted(rows, key=sort_key)[:10]
    tables = (
        ReportTable(
            "address_registry_identity",
            "核心地址一覽",
            ("調查角色", "完整地址（地址編號）", "資產", "流入／流出金額", "優先級"),
            tuple(rows),
        ),
    )
    return replace_section(
        section,
        title="核心地址一覽表",
        content_blocks=(
            "本表只列正文所需核心地址；主要角色與次要活動分行呈現，"
            "避免將雙向活動誤讀為同一角色。完整 Evidence mapping 另存於 "
            "address_registry.csv。",
        ),
        tables=tables,
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
