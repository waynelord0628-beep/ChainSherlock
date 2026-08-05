import ast
from dataclasses import replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from zoneinfo import ZoneInfo

from crypto_investigator.reports.formatting import (
    abbreviate_identifier,
    format_amount,
    format_datetime,
    format_duration,
    format_percent,
)
from crypto_investigator.reports.forensic_artifacts import (
    suspicious_trx_candidates,
    trx_reconciliation,
)
from crypto_investigator.reports.models import ReportSection, ReportTable


ISO_DATETIME = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
NAIVE_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?![.\dZ+-])")
IDENTIFIER = re.compile(
    r"(?:0x[a-fA-F0-9]{40,64}|T[1-9A-HJ-NP-Za-km-z]{33}|"
    r"(?<![A-Za-z0-9.])(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{20,70})"
)


def display_timezone(timezone: str) -> str:
    return "UTC+8（Asia/Taipei）" if timezone == "Asia/Taipei" else timezone


def format_display_text(value, timezone: str) -> str:
    text = str(value)
    text = ISO_DATETIME.sub(
        lambda match: format_datetime(match.group(0), timezone),
        text,
    )
    text = NAIVE_DATETIME.sub(
        lambda match: f"{match.group(0).replace('T', ' ')}（timezone unknown）",
        text,
    )
    replacements = {
        "Confirmed Data Facts": "已確認資料事實",
        "Deterministic Observations": "規則式觀察",
        "Operation Stages": "運作階段",
        "full_history": "完整歷史",
        "complete": "完整",
        "material": "重要資產",
        "candidate": "候選",
        "batch rule": "批次規則",
        "Deterministic ranking": "規則式排名",
    }
    for source, target in replacements.items():
        text = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source)}(?![A-Za-z0-9_])",
            target,
            text,
        )
    return text


def _display_cell(value: str, column: str, timezone: str) -> str:
    text = format_display_text(value, timezone)
    if "完整地址" not in column:
        text = IDENTIFIER.sub(
            lambda match: abbreviate_identifier(match.group(0)),
            text,
        )
    return text


def _address_reference(address: str, registry: dict[str, str]) -> str:
    """Return the stable compact representation used by narrow tables."""
    return f"{registry.get(address, '—')}\n{abbreviate_identifier(address)}"


def _full_address_reference(address: str, registry: dict[str, str]) -> str:
    """Return the complete, copy-safe representation used by the key index."""
    return f"{address}（{registry.get(address, '—')}）"


def _artifact_evidence(evidence):
    selected = {}
    for item in evidence:
        key = (item.source, item.hash or "")
        current = selected.get(key)
        if current is None or (
            str(current.evidence_id).startswith("IF")
            and not str(item.evidence_id).startswith("IF")
        ):
            selected[key] = item
    return tuple(
        selected[key]
        for key in sorted(selected, key=lambda item: (str(item[0]), str(item[1])))
    )


def _row_mapping(table):
    return {str(row[0]): str(row[1]) for row in table.rows if len(row) >= 2}


def _graph_truncated(document) -> bool:
    if any(item.code == "graph_truncated" for item in document.limitations):
        return True
    return any(
        "graph_truncated" in str(row[0]) and str(row[1]).casefold() == "true"
        or "交易關係圖因安全上限發生截斷" in str(row[0])
        for section in document.sections
        for table in section.tables
        if table.table_id == "investigation_facts"
        for row in table.rows
        if len(row) >= 2
    )


def _provider_truncated(document) -> bool:
    table = _find_table(document, "providers")
    if not table or "截斷" not in table.columns:
        return False
    index = table.columns.index("截斷")
    return any(
        str(row[index]).casefold() in {"true", "yes", "是", "1"}
        for row in table.rows
        if len(row) > index
    )


def _confirmed_fact_table(document) -> ReportTable:
    summary = _row_mapping(_find_table(document, "summary") or ReportTable(
        "empty", "empty", (), ()
    ))
    assets = "、".join(_material_assets(document)) or "無可用資料"
    completeness = "完整" if document.metadata.analysis_completeness == "complete" else "部分"
    graph = "已截斷" if _graph_truncated(document) else "未標示截斷"
    provider = "已截斷" if _provider_truncated(document) else "未標示截斷"
    rows = (
        ("FACT-SCOPE-001", "分析標的與鏈別", f"{document.metadata.target_address}／{document.metadata.chain}", "analysis.json", completeness, ""),
        ("FACT-COUNT-001", "分析範圍內交易總數", f"{document.metadata.transaction_count:,}", "analysis.json", completeness, f"其中 {summary.get('unclassified_direction_count', '0')} 筆方向未分類"),
        ("FACT-DIRECTION-001", "流入／流出／未分類筆數", f"{summary.get('incoming_count', '—')}／{summary.get('outgoing_count', '—')}／{summary.get('unclassified_direction_count', '—')}", "analysis.json", completeness, ""),
        ("FACT-ASSET-USDT-001", "USDT 為主要分析資產", "USDT" if "USDT" in assets else "未列入", "analysis.json", completeness, ""),
        ("FACT-ASSET-TRX-001", "TRX 為主要分析資產", "TRX" if "TRX" in assets else "未列入", "analysis.json", completeness, "TRX material flow 另見 reconciliation"),
        ("FACT-PROVIDER-001", "Provider 取得狀態", provider, "provider_status.json", completeness, "Provider 完整不代表 Graph 完整"),
        ("FACT-GRAPH-001", "Graph 安全上限狀態", graph, "flow_graph.json", "部分" if _graph_truncated(document) else completeness, "Graph 截斷不影響 Provider 原始取得完整度"),
    )
    return ReportTable(
        "confirmed_data_facts",
        "已確認資料事實",
        ("事實編號", "事實內容", "數值", "來源", "完整度", "限制"),
        rows,
    )


def _additional_observation_table(document) -> ReportTable:
    patterns = _row_mapping(_find_table(document, "transfer_patterns") or ReportTable(
        "empty", "empty", (), ()
    ))
    rows = (
        ("OBS-BATCH-IN-001", f"目前分析範圍內辨識到 {patterns.get('批次流入視窗數', patterns.get('batch_incoming_count', '0'))} 個批次流入視窗。", "規則式計算", "中", "批次視窗不代表共同控制人"),
        ("OBS-BATCH-OUT-001", f"目前分析範圍內辨識到 {patterns.get('批次流出視窗數', patterns.get('batch_outgoing_count', '0'))} 個批次流出視窗。", "規則式計算", "中", "批次視窗不代表同一資金路徑"),
        ("OBS-FIXED-USDT-001", "USDT 存在重複固定金額模式。", "規則式計算", "中", "完整金額清單見 fixed_amounts.csv"),
        ("OBS-FIXED-TRX-001", "TRX 存在重複固定金額模式；可疑宣傳型候選已另行隔離。", "規則式計算", "中", "候選仍待人工覆核"),
        ("OBS-DORMANCY-001", "目前分析範圍內未偵測到符合規則門檻的休眠區間。", "規則式計算", "中", "門檻及資料範圍可能影響結果"),
        ("OBS-STAGE-001", "目前資料可分為啟動期與來源多元化階段。", "規則式計算", "中", "階段由 deterministic 規則產生"),
    )
    return ReportTable(
        "rule_observation_summary",
        "模式與階段觀察",
        ("Observation ID", "規則式觀察", "來源", "信心", "資料限制"),
        rows,
    )


def _material_assets(document) -> tuple[str, ...]:
    ranked = []
    for section in document.sections:
        for table in section.tables:
            if table.table_id != "asset_flows":
                continue
            for row in table.rows:
                try:
                    count = int(str(row[3]).replace(",", ""))
                except (IndexError, TypeError, ValueError):
                    count = 0
                ranked.append((count, str(row[0])))
    selected = tuple(asset for count, asset in sorted(ranked, reverse=True) if count > 1)
    return selected or tuple(asset for _, asset in sorted(ranked, reverse=True)[:5])


def _material_table(table, assets, sources, destinations):
    if table.table_id in {"summary", "confirmed_data_facts"}:
        rows = tuple(
            (
                (row[0], "、".join(assets), *row[2:])
                if row and str(row[0]) in {"主要資產", "重要資產", "main_assets"}
                else row
            )
            for row in table.rows
        )
        return replace(table, rows=rows)
    if table.table_id in {"asset_flows", "asset_time_scope", "holding_time"}:
        rows = tuple(row for row in table.rows if str(row[0]) in assets)
        return replace(table, rows=rows, omitted_count=len(table.rows) - len(rows))
    if table.table_id == "funding_sources":
        rows = tuple(row for row in table.rows if str(row[1]) in assets)
        return replace(table, rows=rows, omitted_count=len(table.rows) - len(rows))
    if table.table_id == "operation_stages":
        rows = []
        for row in table.rows:
            values = list(row)
            values[4] = "、".join(assets)
            values[5] = "、".join(sources[:3]) or "unavailable"
            values[6] = "、".join(destinations[:3]) or "unavailable"
            rows.append(tuple(values))
        return replace(table, rows=tuple(rows))
    return table


def _apply_address_registry(table, registry):
    if "地址" in table.columns:
        index = table.columns.index("地址")
        columns = list(table.columns)
        columns[index] = "完整地址"
        columns.insert(index, "地址編號")
        rows = []
        for row in table.rows:
            values = list(row)
            address = str(values[index])
            values.insert(index, registry.get(address, "—"))
            rows.append(tuple(values))
        return replace(table, columns=tuple(columns), rows=tuple(rows))
    if table.table_id in {
        "funding_transitions",
        "operation_stages",
        "investigation_observations",
        "investigation_facts",
    }:
        return replace(
            table,
            rows=tuple(
                tuple(
                    IDENTIFIER.sub(
                        lambda match: registry.get(match.group(0), match.group(0)),
                        str(value),
                    )
                    for value in row
                )
                for row in table.rows
            ),
        )
    return table


def _format_numeric_table(table):
    amount_markers = ("金額", "流入", "流出", "配對", "未配對")
    rows = []
    asset_index = next(
        (index for index, value in enumerate(table.columns) if value == "資產"),
        None,
    )
    for row in table.rows:
        asset = str(row[asset_index]).upper() if asset_index is not None else ""
        values = []
        for index, value in enumerate(row):
            column = str(table.columns[index])
            text = str(value)
            if any(marker in column for marker in amount_markers):
                try:
                    number = Decimal(text.replace(",", ""))
                except InvalidOperation:
                    pass
                else:
                    if number and abs(number) < Decimal("0.00000001"):
                        text = f"{number:.2E}"
                    else:
                        text = _display_amount_2(number)
            elif any(marker in column for marker in ("筆數", "交易數", "事件數")):
                try:
                    text = f"{int(text.replace(',', '')):,}"
                except ValueError:
                    pass
            values.append(text)
        rows.append(tuple(values))
    return replace(table, rows=tuple(rows))


def _address_registry_tables(addresses, registry, chain):
    rows = tuple(
        (
            registry[address],
            chain or "unavailable",
            address,
            "未標記",
            "候選角色未確認",
            "主文表格／調查 artifact",
            "完整值供查核與複製",
        )
        for address in addresses
    )
    return (
        ReportTable(
            "address_registry_identity",
            "地址對照表（身分資料）",
            ("地址編號", "鏈別", "完整地址", "人工 Label"),
            tuple((row[0], row[1], row[2], row[3]) for row in rows),
        ),
        ReportTable(
            "address_registry_context",
            "地址對照表（調查脈絡）",
            ("地址編號", "候選角色", "Label", "主要用途／出現章節"),
            tuple(
                (
                    row[0],
                    row[4],
                    row[3],
                    "主文排名、規則式觀察或候選摘要",
                )
                for row in rows
            ),
        ),
    )


def address_registry_rows(document):
    """Return the stable, complete address registry used by every exporter."""
    all_addresses = {
        match.group(0)
        for section in document.sections
        for value in (
            *section.content_blocks,
            *(
                cell
                for table in section.tables
                for row in table.rows
                for cell in row
            ),
        )
        for match in IDENTIFIER.finditer(str(value))
    }
    target = document.metadata.target_address
    ordered = []

    def add(address):
        if address in all_addresses and address not in ordered:
            ordered.append(address)

    add(target)
    assets = list(_material_assets(document))
    assets = [item for item in ("USDT", "TRX") if item in assets] + [
        item for item in assets if item not in {"USDT", "TRX"}
    ]
    funding = next(
        (
            table
            for section in document.sections
            for table in section.tables
            if table.table_id == "funding_sources"
        ),
        None,
    )
    counterparty_summary = next(
        (
            table
            for section in document.sections
            for table in section.tables
            if table.table_id == "counterparty_summary"
        ),
        None,
    )
    counterparties = counterparty_summary or next(
        (
            table
            for section in document.sections
            for table in section.tables
            if table.table_id == "counterparties"
        ),
        None,
    )
    ranked_groups = []
    for asset in assets:
        sources = [
            row for row in (funding.rows if funding else ())
            if len(row) >= 7 and str(row[1]) == asset
        ]
        sources.sort(
            key=lambda row: (
                -_number(row[3]),
                -_number(row[4]),
                str(row[5]),
                str(row[2]),
            )
        )
        peers = [
            row for row in (counterparties.rows if counterparties else ())
            if len(row) >= 10 and str(row[4]) == asset
        ]
        outgoing = sorted(
            (row for row in peers if str(row[2]) == "流出"),
            key=lambda row: (
                -_number(row[6]),
                -_number(row[3]),
                str(row[7]),
                str(row[1]),
            ),
        )
        frequent = sorted(
            peers,
            key=lambda row: (
                -_number(row[3]),
                -max(_number(row[5]), _number(row[6])),
                str(row[7]),
                str(row[1]),
            ),
        )
        ranked_groups.append((sources, outgoing, frequent))
    for sources, outgoing, frequent in ranked_groups:
        if sources:
            add(str(sources[0][2]))
        if outgoing:
            add(str(outgoing[0][1]))
        if frequent:
            add(str(frequent[0][1]))
    for sources, outgoing, frequent in ranked_groups:
        for row in sources[1:10]:
            add(str(row[2]))
        for row in (*outgoing[:10], *frequent[:10]):
            add(str(row[1]))
    ordered.extend(sorted(all_addresses - set(ordered)))
    return tuple(
        (
            f"地址-{index:03d}",
            document.metadata.chain or "unavailable",
            address,
            "調查標的" if address == target else "未標記",
            "本案主地址" if address == target else "候選角色未確認",
            "ReportDocument",
            "完整值供查核與複製",
        )
        for index, address in enumerate(ordered, 1)
    )


def _number(value) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except InvalidOperation:
        return Decimal(0)


def _display_amount_2(value) -> str:
    """Format booklet amounts compactly without changing stored precision."""
    try:
        number = Decimal(str(value).replace(",", ""))
    except InvalidOperation:
        return str(value)
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}"


def _find_table(document, table_id):
    return next(
        (
            table
            for section in document.sections
            for table in section.tables
            if table.table_id == table_id
        ),
        None,
    )


def _asset_first_sections(document, registry, material_assets):
    asset_flows = _find_table(document, "asset_flows")
    funding = _find_table(document, "funding_sources")
    counterparties = (
        _find_table(document, "counterparty_summary")
        or _find_table(document, "counterparties")
    )
    assets = [asset for asset in ("USDT", "TRX") if asset in material_assets]
    assets.extend(
        asset for asset in material_assets
        if asset not in assets
    )

    def address_id(address):
        return registry.get(address, "—")

    important_address_roles = {}

    def add_role(target_map, address, role):
        if not address:
            return
        roles = target_map.setdefault(address, [])
        if role not in roles:
            roles.append(role)

    def add_important_role(address, role):
        add_role(important_address_roles, address, role)

    target = document.metadata.target_address
    if target:
        add_important_role(target, "調查標的")
    sections = []
    all_ranking_rows = []
    path_rows = []
    trx_candidates = suspicious_trx_candidates(document)
    quarantined_trx_senders = {item["sender"] for item in trx_candidates}
    trx_totals = trx_reconciliation(document)
    for asset_index, asset in enumerate(assets):
        asset_row = next(
            (
                row for row in (asset_flows.rows if asset_flows else ())
                if str(row[0]) == asset
            ),
            None,
        )
        summary_rows = (
            (
                asset,
                _display_amount_2(asset_row[1]),
                _display_amount_2(asset_row[2]),
                str(asset_row[3]),
                "主要分析資產",
            ),
        ) if asset_row else ()

        all_source_rows = [
            row for row in (funding.rows if funding else ())
            if len(row) >= 7 and str(row[1]) == asset
        ]
        source_rows = [
            row
            for row in all_source_rows
            if asset != "TRX" or str(row[2]) not in quarantined_trx_senders
        ]
        source_rows.sort(
            key=lambda row: (
                -_number(row[3]),
                -_number(row[4]),
                str(row[5]),
                str(row[2]),
            )
        )
        source_table_rows = tuple(
            (
                str(rank),
                _address_reference(str(row[2]), registry),
                _display_amount_2(row[3]),
                str(row[4]),
                str(row[5]),
                str(row[6]),
            )
            for rank, row in enumerate(source_rows[:10], 1)
        )
        asset_counterparties = [
            row for row in (counterparties.rows if counterparties else ())
            if len(row) >= 10 and str(row[4]) == asset
        ]
        outgoing = [row for row in asset_counterparties if str(row[2]) == "流出"]
        outgoing.sort(
            key=lambda row: (
                -_number(row[6]),
                -_number(row[3]),
                str(row[7]),
                str(row[1]),
            )
        )
        frequent = sorted(
            asset_counterparties,
            key=lambda row: (
                -_number(row[3]),
                -max(_number(row[5]), _number(row[6])),
                str(row[7]),
                str(row[1]),
            ),
        )

        def counterparty_rows(records, amount_index):
            return tuple(
                (
                    str(rank),
                    _address_reference(str(row[1]), registry),
                    str(row[2]),
                    str(row[3]),
                    _display_amount_2(row[amount_index]),
                    str(row[7]),
                    str(row[8]),
                )
                for rank, row in enumerate(records[:10], 1)
            )

        outgoing_rows = counterparty_rows(outgoing, 6)
        frequent_rows = counterparty_rows(frequent, 6)
        if source_rows:
            address = str(source_rows[0][2])
            add_important_role(address, f"{asset} 主要來源")
        if outgoing:
            address = str(outgoing[0][1])
            add_important_role(address, f"{asset} 主要去向")
        if frequent:
            address = str(frequent[0][1])
            add_important_role(address, f"{asset} 高頻交易對手")

        for category, rows in (
            ("主要資金來源", source_table_rows),
            ("主要資金去向", outgoing_rows),
            ("高頻交易對手", frequent_rows),
        ):
            for row in rows[:3]:
                all_ranking_rows.append((asset, category, *row[:2]))

        if source_rows and outgoing and target:
            source_address = str(source_rows[0][2])
            destination = str(outgoing[0][1])
            path_rows.append(
                (
                    f"FLOW-SUMMARY-{len(path_rows) + 1:03d}",
                    asset,
                    registry.get(source_address, "—"),
                    registry.get(target, "—"),
                    registry.get(destination, "—"),
                    _display_amount_2(source_rows[0][3]),
                    _display_amount_2(outgoing[0][6]),
                    "來源與去向排名組合",
                    "候選摘要",
                    f"CAND-FLOW-{asset}-001",
                    "不代表同一筆資金之確定流向；來源與去向金額分別計算。",
                )
            )

        narrative = [
            f"在本次分析範圍內，{asset} 共納入 "
            f"{str(asset_row[3]) if asset_row else 'unavailable'} 筆交易；"
            f"流入金額為 {_display_amount_2(asset_row[1]) if asset_row else 'unavailable'}，"
            f"流出金額為 {_display_amount_2(asset_row[2]) if asset_row else 'unavailable'}。",
        ]
        if source_rows:
            source_address = str(source_rows[0][2])
            narrative.append(
                f"最大資金來源為 {abbreviate_identifier(source_address)}"
                f"（{registry.get(source_address, '—')}），"
                f"目前範圍內流入金額 {_display_amount_2(source_rows[0][3])}、"
                f"占比 {source_rows[0][4]}。"
            )
        else:
            narrative.append("目前結構化結果未提供可排名的主要資金來源。")
        if outgoing:
            destination = str(outgoing[0][1])
            narrative.append(
                f"最大資金去向為 {abbreviate_identifier(destination)}"
                f"（{registry.get(destination, '—')}），"
                f"目前範圍內流出金額 {_display_amount_2(outgoing[0][6])}。"
            )
        else:
            narrative.append("目前結構化結果未提供可排名的主要資金去向。")
        if frequent:
            address = str(frequent[0][1])
            narrative.append(
                f"互動最頻繁的交易對手為 {abbreviate_identifier(address)}"
                f"（{registry.get(address, '—')}），"
                f"共 {frequent[0][3]} 次。"
            )

        tables = [
            ReportTable(
                f"asset_summary_{asset.casefold()}",
                f"{asset} 資產摘要",
                ("資產", "流入金額", "流出金額", "交易數", "資料狀態"),
                summary_rows,
            ),
            ReportTable(
                f"funding_rank_{asset.casefold()}",
                f"{asset} 主要資金來源 Top 10（依流入金額）",
                ("排名", "地址參照", "流入金額", "占比", "首次", "最後"),
                source_table_rows,
            ),
            ReportTable(
                f"outgoing_rank_{asset.casefold()}",
                f"{asset} 主要資金去向 Top 10（依流出金額）",
                ("排名", "地址參照", "方向", "交易次數", "流出金額"),
                tuple(row[:5] for row in outgoing_rows),
            ),
            ReportTable(
                f"outgoing_time_{asset.casefold()}",
                f"{asset} 主要資金去向時間對照",
                ("排名", "地址編號", "首次", "最後"),
                tuple(
                    (row[0], row[1].splitlines()[0], row[5], row[6])
                    for row in outgoing_rows
                ),
            ),
            ReportTable(
                f"frequency_rank_{asset.casefold()}",
                f"{asset} 高頻交易對手 Top 10（依交易次數）",
                ("排名", "地址參照", "方向", "交易次數", "流出金額"),
                tuple(row[:5] for row in frequent_rows),
            ),
            ReportTable(
                f"frequency_time_{asset.casefold()}",
                f"{asset} 高頻交易對手時間對照",
                ("排名", "地址編號", "首次", "最後"),
                tuple(
                    (row[0], row[1].splitlines()[0], row[5], row[6])
                    for row in frequent_rows
                ),
            ),
        ]
        if asset == "TRX":
            tables.insert(
                1,
                ReportTable(
                    "trx_flow_reconciliation",
                    "TRX 鏈上、重要與隔離流入",
                    ("分類", "金額", "狀態", "限制"),
                    (
                        ("鏈上總流入", _display_amount_2(trx_totals["gross_on_chain_inflow"]), "完整歷史彙總", ""),
                        ("重要資金流入", _display_amount_2(trx_totals["final_material_inflow"]), "候選隔離後", "尚待人工覆核"),
                        ("宣傳型轉入候選", _display_amount_2(trx_totals["promotional_candidate"]), "候選", "未確認為釣魚或詐騙"),
                        ("尚待人工覆核", _display_amount_2(trx_totals["promotional_candidate"]), "未審閱", "可逆並可重新納入"),
                    ),
                ),
            )
            candidate_rows = tuple(
                (
                    _address_reference(str(item["sender"]), registry),
                    _display_amount_2(item["normalized_amount"]),
                    str(item["timestamp"]),
                    str(item["same_amount_source_count"]),
                    f"CAND-TRX-{candidate_index:03d}",
                )
                for candidate_index, item in enumerate(trx_candidates, 1)
            )
            tables.append(
                ReportTable(
                    "suspicious_trx_transfers",
                    "TRX 可疑轉入候選（金額與時間）",
                    ("地址參照", "金額", "交易時間", "同額來源數", "候選編號"),
                    candidate_rows,
                )
            )
            tables.append(
                ReportTable(
                    "suspicious_trx_review",
                    "TRX 可疑轉入候選（分類與覆核）",
                    ("候選編號", "候選類型", "原因", "信心", "人工審閱"),
                    tuple(
                        (
                            f"CAND-TRX-{candidate_index:03d}",
                            "宣傳型轉入候選",
                            "醒目固定金額且由多個來源地址出現同額轉入",
                            "中",
                            "尚未審閱",
                        )
                        for candidate_index, _item in enumerate(trx_candidates, 1)
                    ),
                )
            )
        sections.append(
            ReportSection(
                f"asset_analysis_{asset.casefold()}",
                f"{asset} 分析",
                50 + asset_index,
                tuple(narrative) + (
                    f"以下依序呈現 {asset} 的來源、去向及互動頻率排名；三種排名不得混為同一結論。",
                    "地址編號是全報告固定索引，不等於本表排名；排名以最左欄為準。重要地址已於前段對照，其餘完整地址保留於後段地址對照表及 address_registry.csv。",
                ),
                tables=tuple(tables),
            )
        )

    existing_labels = {
        str(row[address_index]): str(row[label_index])
        for source_section in document.sections
        for table in source_section.tables
        if "完整地址" in table.columns and "人工 Label" in table.columns
        for address_index in (table.columns.index("完整地址"),)
        for label_index in (table.columns.index("人工 Label"),)
        for row in table.rows
        if len(row) > max(address_index, label_index)
        and str(row[label_index]) not in {"", "未標記", "unavailable", "—"}
    }
    for address, label in existing_labels.items():
        add_important_role(address, f"人工標籤：{label}")
    for source_section in document.sections:
        if not source_section.section_id.startswith("ai_"):
            continue
        for value in (
            *source_section.content_blocks,
            *(
                cell
                for table in source_section.tables
                for row in table.rows
                for cell in row
            ),
        ):
            for match in IDENTIFIER.finditer(str(value)):
                add_important_role(match.group(0), "AI／綜合研判引用")

    important_rows = tuple(
        (
            "／".join(roles),
            _full_address_reference(address, registry),
        )
        for address, roles in sorted(
            important_address_roles.items(),
            key=lambda item: address_id(item[0]),
        )
    )

    return (
        ReportSection(
            "key_addresses",
            "關鍵地址與角色摘要",
            30,
            (
                "本節先列出主文反覆引用的重要地址。完整地址可直接複製；"
                "括號內地址編號為本報告固定索引，候選角色不代表身分已確認。",
            ),
            tables=(
                ReportTable(
                    "key_address_summary",
                    "重要地址一覽表",
                    ("角色", "完整地址（地址編號）"),
                    important_rows,
                ),
            ),
        ),
        *sections,
        ReportSection(
            "address_rankings",
            "地址排名總覽",
            100,
            ("排名依幣種及用途分開計算，不以地址編號或內部資料順序排序。",),
            tables=(
                ReportTable(
                    "address_ranking_overview",
                    "重要地址排名摘要",
                    ("資產", "排名類型", "排名", "地址編號"),
                    tuple(all_ranking_rows),
                ),
            ),
        ),
        ReportSection(
            "fund_flow_paths",
            "主要來源與去向關聯摘要",
            110,
            (
                "本節僅將各資產最大來源與最大去向並列，未執行 transaction-level "
                "path tracing；不得視為同一筆資金的確定流向。",
            ),
            tables=(
                ReportTable(
                    "fund_flow_paths",
                    "地址層級候選流向摘要",
                    ("摘要 ID", "資產", "主要來源", "調查標的", "主要去向", "來源金額", "去向金額"),
                    tuple(row[:7] for row in path_rows),
                ),
                ReportTable(
                    "fund_flow_path_context",
                    "候選摘要方法與限制",
                    ("摘要 ID", "關聯方法", "狀態", "Candidate ID", "限制"),
                    tuple((row[0], *row[7:]) for row in path_rows),
                ),
            ),
        ),
    )


def _reorder_booklet(document, sections, registry, material_assets):
    generated = _asset_first_sections(document, registry, material_assets)
    booklet_assets = tuple(
        asset for asset in ("USDT", "TRX") if asset in material_assets
    ) + tuple(
        asset for asset in material_assets if asset not in {"USDT", "TRX"}
    )
    excluded = {
        "counterparties",
        "funding_analysis",
        "outgoing_distribution",
        "data_pipeline",
        "provider_status",
        "provider_errors",
        "rejected_records",
        "direction_reconciliation",
        "investigation",
        "investigation_facts",
        "data_sources",
    }
    base = [section for section in sections if section.section_id not in excluded]
    appendix = next(
        (section for section in base if section.section_id == "appendix"),
        None,
    )
    if appendix:
        registry_tables = tuple(
            table for table in appendix.tables
            if table.table_id.startswith("address_registry_")
        )
        base = [
            replace(
                section,
                tables=tuple(
                    table for table in section.tables
                    if not table.table_id.startswith("address_registry_")
                ),
            )
            if section.section_id == "appendix"
            else section
            for section in base
        ]
        if registry_tables:
            base.append(
                ReportSection(
                    "address_registry",
                    "地址對照表",
                    220,
                    (
                        "下列地址均為主文引用地址；若無人工或 Local Label，角色保持未確認。"
                        "完整證據 mapping 請參閱 report_data.json；其餘地址請參閱 "
                        "address_registry.csv。",
                    ),
                    tables=registry_tables,
                )
            )
    toc_titles = (
        "執行摘要",
        "調查標的與分析範圍",
        "關鍵地址與角色摘要",
        "資產總覽",
        *(f"{asset} 分析" for asset in booklet_assets),
        "地址排名總覽",
        "主要來源與去向關聯摘要",
        "時間軸與運作階段",
        "固定金額、批次與停留時間",
        "已確認事實",
        "規則式觀察",
        "候選解釋",
        "AI 專業綜合",
        "尚待查證",
        "後續調查建議",
        "資料限制",
        "綜合研判",
        "Evidence Index",
        "附錄",
        "地址對照表",
    )
    toc = ReportSection(
        "table_of_contents",
        "目錄",
        2,
        tuple(f"{index}. {title}" for index, title in enumerate(toc_titles, 1)),
    )
    order_map = {
        "cover": 1,
        "table_of_contents": 2,
        "executive_summary": 10,
        "analysis_summary": 11,
        "target": 20,
        "completeness": 21,
        "key_addresses": 30,
        "asset_flows": 40,
        "address_rankings": 100,
        "fund_flow_paths": 110,
        "graph": 111,
        "timeline": 120,
        "operation_stages": 121,
        "holding_time": 122,
        "transfer_patterns": 123,
        "dormancy": 124,
        "confirmed_facts": 130,
        "investigation_facts": 131,
        "investigation_observations": 140,
        "observations": 141,
        "candidate_interpretations": 142,
        "unresolved_questions": 170,
        "recommended_follow_up": 171,
        "limitations": 180,
        "conclusion": 190,
        "evidence_index": 200,
        "non_material_assets": 209,
        "appendix": 210,
        "address_registry": 220,
    }
    ai_sections = [section for section in base if section.section_id.startswith("ai_")]
    base = [section for section in base if not section.section_id.startswith("ai_")]
    ordered = []
    for section in (*base, toc, *generated, *ai_sections):
        if section.section_id.startswith("asset_analysis_"):
            order = section.order
        elif section.section_id.startswith("ai_"):
            order = 150 + ai_sections.index(section)
        else:
            order = order_map.get(section.section_id, section.order + 300)
        ordered.append(replace(section, order=order))
    return tuple(sorted(ordered, key=lambda item: (item.order, item.section_id)))


def _formalize_table(table):
    if table.table_id == "investigation_facts":
        replacements = {
            "funding transition count": "主要供款來源切換次數",
            "longest dormant days": "最長休眠天數",
            "service candidate count": "服務型態候選數",
            "unknown direction count": "方向未分類筆數",
        }
        rows = []
        for row in table.rows:
            text = str(row[0])
            for source, target in replacements.items():
                text = re.sub(source, target, text, flags=re.IGNORECASE)
            text = re.sub(r"(\d+)\s+count", r"\1 筆", text)
            text = re.sub(r"(\d+)\s+days", r"\1 天", text)
            rows.append((text, *row[1:]))
        table = replace(table, rows=tuple(rows))
    if table.table_id == "summary" and any(
        str(row[0]) == "first_seen" for row in table.rows
    ):
        values = _row_mapping(table)
        labels = (
            ("first_seen", "分析起始時間"),
            ("last_seen", "分析結束時間"),
            ("transaction_count", "分析交易筆數"),
            ("incoming_count", "流入交易筆數"),
            ("outgoing_count", "流出交易筆數"),
            ("unclassified_direction_count", "未分類方向筆數"),
            ("main_assets", "主要資產"),
            ("unique_counterparties", "主要交易對手數"),
            ("analysis_completeness", "資料完整度"),
        )
        return replace(
            table,
            rows=tuple((label, values[key]) for key, label in labels if key in values),
        )
    if table.table_id == "counterparties" and "address" in table.columns:
        return ReportTable(
            table.table_id,
            "主要交易對手",
            ("排名", "地址", "方向", "交易次數", "主要資產",
             "流入金額", "流出金額", "首次出現", "最後出現", "標籤／候選角色"),
            tuple(
                (
                    str(rank),
                    row[0],
                    row[6],
                    row[3],
                    "—",
                    "—",
                    "—",
                    row[4],
                    row[5],
                    "—",
                )
                for rank, row in enumerate(table.rows, 1)
            ),
        )
    if table.table_id == "providers" and len(table.columns) > 8:
        index = {name: position for position, name in enumerate(table.columns)}
        fields = (
            ("chain", "鏈別"),
            ("capability", "Capability"),
            ("provider", "Provider"),
            ("fetched_records", "取得筆數"),
            ("completeness", "完整度"),
            ("truncated", "截斷"),
            ("truncation_reason", "截斷原因"),
            ("warnings", "警告"),
        )
        return ReportTable(
            table.table_id,
            table.title,
            tuple(label for _, label in fields),
            tuple(
                tuple(row[index[key]] if key in index else "—" for key, _ in fields)
                for row in table.rows
            ),
        )
    if table.table_id == "funding_transitions" and "asset" in table.columns:
        index = {name: position for position, name in enumerate(table.columns)}
        fields = (
            ("asset", "資產"),
            ("previous_source", "前一主要來源"),
            ("current_source", "新主要來源"),
            ("occurred_at", "發生時間"),
            ("old_source_share", "前一占比"),
            ("new_source_share", "新占比"),
            ("reason_codes", "原因"),
        )
        rows = []
        for row in table.rows:
            values = [row[index[key]] if key in index else "—" for key, _ in fields]
            for position in (4, 5):
                try:
                    values[position] = format_percent(values[position])
                except Exception:
                    pass
            rows.append((*values, "低", "部分資料可能改變判定"))
        return ReportTable(
            table.table_id,
            "供款來源變化",
            tuple(label for _, label in fields) + ("信心", "限制"),
            tuple(rows),
        )
    if table.table_id == "holding_time" and "平均秒數" in table.columns:
        rows = []
        for row in table.rows:
            values = list(row)
            values[5] = format_duration(values[5])
            values[6] = format_duration(values[6])
            values[8] = format_percent(values[8])
            values[9] = format_percent(values[9])
            rows.append(tuple(values[:7] + values[8:]))
        return ReportTable(
            table.table_id,
            table.title,
            ("資產", "配對流入", "配對流出", "未配對流入", "未配對流出",
             "平均停留時間", "中位停留時間", "1 小時內比例", "24 小時內比例", "事件數"),
            tuple(rows),
        )
    if table.table_id == "transfer_patterns" and any(
        str(row[0]) in {"fixed_amounts", "主要固定金額"} for row in table.rows
    ):
        values = _row_mapping(table)
        fixed = []
        try:
            parsed = ast.literal_eval(values.get("fixed_amounts", "{}"))
            for asset, amounts in sorted(parsed.items()):
                for rank, item in enumerate(amounts[:8], 1):
                    fixed.append(
                        (
                            str(asset),
                            str(rank),
                            format_amount(item),
                            "未保存",
                            "未保存",
                            f"OBS-FIXED-{str(asset).upper()}-{rank:03d}",
                        )
                    )
        except (SyntaxError, ValueError):
            pass
        if not fixed:
            for group in values.get("主要固定金額", "").split("；"):
                if "：" not in group:
                    continue
                asset, amounts = group.split("：", 1)
                for rank, item in enumerate(amounts.split("、")[:8], 1):
                    if item:
                        fixed.append(
                            (
                                asset,
                                str(rank),
                                format_amount(str(item).replace(",", "")),
                                "未保存",
                                "未保存",
                                f"OBS-FIXED-{asset.upper()}-{rank:03d}",
                            )
                        )
        return ReportTable(
            table.table_id,
            "主要固定金額",
            ("資產", "排名", "固定金額", "出現次數", "占比", "Observation ID"),
            tuple(fixed),
        )
    if table.table_id == "investigation_observations":
        funding_index = 0
        rows = []
        for row in table.rows:
            if len(table.columns) > 4:
                statement, confidence, limitation = row[1], row[5], row[6]
            elif len(row) >= 4:
                statement, confidence, limitation = row[0], row[2], row[3]
            elif len(row) >= 2:
                statement, confidence, limitation = (
                    row[1],
                    "medium",
                    "僅反映目前分析範圍",
                )
            else:
                statement, confidence, limitation = (
                    row[0],
                    "medium",
                    "僅反映目前分析範圍",
                )
            statement = str(statement).replace("batch rule", "批次規則")
            if "主要供款來源" in statement:
                funding_index += 1
                claim_id = f"OBS-FUNDING-{funding_index:03d}"
            elif "批次流入" in statement:
                claim_id = "OBS-BATCH-IN-001"
            elif "批次流出" in statement:
                claim_id = "OBS-BATCH-OUT-001"
            else:
                claim_id = f"OBS-RULE-{len(rows) + 1:03d}"
            rows.append(
                (
                    claim_id,
                    statement,
                    "規則式計算",
                    "中" if str(confidence).casefold() == "medium" else "高",
                    str(limitation) or "僅反映目前分析範圍",
                )
            )
        return ReportTable(
            table.table_id,
            "規則式觀察",
            ("Observation ID", "規則式觀察", "來源", "信心", "資料限制"),
            tuple(rows),
        )
    if table.table_id == "counterparty_summary" and len(table.columns) > 10:
        return ReportTable(
            table.table_id,
            table.title,
            ("排名", "地址", "方向", "交易次數", "主要資產",
             "流入金額", "流出金額", "首次出現", "最後出現", "標籤／候選角色"),
            tuple(
                (
                    row[0], row[1], row[4], row[5], row[6],
                    row[7], row[8], row[10], row[11],
                    row[2] if row[2] != "—" else row[3],
                )
                for row in table.rows
            ),
        )
    return table


def _evidence_table(evidence):
    rows = []
    type_labels = {
        "analysis": "分析結果",
        "flow_graph": "關係圖",
        "investigation": "調查特徵",
        "investigation_artifact": "調查特徵",
        "provider_errors": "Provider 錯誤",
        "provider_status": "Provider 狀態",
        "rejected_records": "拒絕資料",
    }
    for item in evidence:
        available = bool(item.hash)
        evidence_id = (
            "LEGACY-ARTIFACT"
            if str(item.evidence_id).startswith("IF")
            else str(item.evidence_id)
        )
        rows.append((
            evidence_id,
            str(item.source).replace("\\", "/").rsplit("/", 1)[-1],
            type_labels.get(str(item.evidence_type), str(item.evidence_type)),
            f"{str(item.hash)[:12]}…" if available else "雜湊不可用",
            "已驗證" if available else "無法驗證",
            "雜湊可重新驗證" if available else "舊版 artifact 未提供雜湊",
        ))
    return ReportTable(
        "artifact_evidence_index",
        "證據索引",
        ("Evidence ID", "檔名", "類型", "SHA-256", "完整性", "備註"),
        tuple(rows),
    )


def _stage_address_summary(value, registry) -> str:
    addresses = [match.group(0) for match in IDENTIFIER.finditer(str(value))]
    visible = [
        f"{abbreviate_identifier(address)}（{registry.get(address, '—')}）"
        for address in addresses[:3]
    ]
    remaining = max(0, len(addresses) - len(visible))
    if remaining:
        visible.append(f"另有 {remaining} 個")
    return "、".join(visible) or "資料不足"


def _stage_asset_summary(value) -> str:
    assets = [
        item.strip()
        for item in re.split(r"[、,;；]", str(value))
        if item.strip()
    ]
    visible = assets[:3]
    if len(assets) > len(visible):
        visible.append(f"另有 {len(assets) - len(visible)} 項")
    return "、".join(visible) or "資料不足"


def _operation_stage_tables(table, registry, timezone) -> tuple[ReportTable, ...]:
    index = {name: position for position, name in enumerate(table.columns)}
    tables = []
    previous = None
    confidence_labels = {"low": "低", "medium": "中", "high": "高"}
    for order, row in enumerate(table.rows, 1):
        def value(name, default="資料不足"):
            position = index.get(name)
            return str(row[position]) if position is not None and len(row) > position else default

        stage = value("階段", value("stage", f"階段 {order}"))
        started = value("開始", value("開始時間"))
        ended = value("結束", value("結束時間"))
        count = value("交易數", value("交易筆數"))
        assets = value("資產", value("主要資產"))
        sources = value("主要來源")
        destinations = value("主要去向")
        basis = value("判定依據")
        confidence = confidence_labels.get(
            value("信心").casefold(), value("信心")
        )
        limitation = value("資料限制", "")
        changes = []
        if previous is None:
            changes.append("首個階段，無前一階段可供比較。")
        else:
            previous_count = Decimal(previous["count"])
            current_count = Decimal(count)
            direction = (
                "增加" if current_count > previous_count
                else "減少" if current_count < previous_count
                else "持平"
            )
            changes.append(f"交易筆數較前一階段{direction}。")
            changes.append(
                "主要來源組成未變。"
                if sources == previous["sources"]
                else "主要來源組成發生變化。"
            )
            changes.append(
                "主要去向組成未變。"
                if destinations == previous["destinations"]
                else "主要去向組成發生變化。"
            )
            changes.append(
                "主要資產組成未變。"
                if assets == previous["assets"]
                else "主要資產組成發生變化。"
            )
            changes.append("階段金額彙總未保存，無法判定金額變化。")
        tables.append(
            ReportTable(
                f"operation_stage_{order:02d}",
                f"運作階段：{stage}",
                ("項目", "內容"),
                (
                    ("期間", f"{format_display_text(started, timezone)} 至 {format_display_text(ended, timezone)}"),
                    ("交易數", count),
                    ("主要資產", _stage_asset_summary(assets)),
                    ("主要來源", _stage_address_summary(sources, registry)),
                    ("主要去向", _stage_address_summary(destinations, registry)),
                    ("判定依據", basis),
                    ("與前期比較", " ".join(changes)),
                    ("信心", confidence),
                    ("限制", limitation or "僅反映目前分析範圍"),
                    ("Observation ID", "OBS-STAGE-001" if order == 1 else f"OBS-STAGE-{order:03d}"),
                ),
            )
        )
        previous = {
            "count": count,
            "sources": sources,
            "destinations": destinations,
            "assets": assets,
        }
    return tuple(tables)


def _split_wide_table(table):
    if table.table_id == "artifact_evidence_index":
        groups = ((0, 1, 2), (0, 3, 4, 5))
        labels = ("識別資訊", "完整性資訊")
        return tuple(
            ReportTable(
                f"{table.table_id}_{index + 1}",
                f"{table.title}（{labels[index]}）",
                tuple(table.columns[position] for position in group),
                tuple(
                    tuple(row[position] for position in group)
                    for row in table.rows
                ),
                table.omitted_count,
            )
            for index, group in enumerate(groups)
        )
    if len(table.columns) <= 6:
        return (table,)
    if table.table_id == "counterparty_summary" and "完整地址" in table.columns:
        groups = ((0, 1, 2), (1, 3, 4, 5), (1, 6, 7, 8, 9), (1, 10))
        labels = ("地址", "關係", "金額與時間", "角色")
        return tuple(
            ReportTable(
                f"{table.table_id}_{index + 1}",
                f"{table.title}（{labels[index]}）",
                tuple(table.columns[position] for position in group),
                tuple(
                    tuple(row[position] for position in group)
                    for row in table.rows
                ),
                table.omitted_count,
            )
            for index, group in enumerate(groups)
        )
    if table.table_id == "funding_sources" and "完整地址" in table.columns:
        groups = ((0, 2, 3), (2, 1, 4, 5), (2, 6, 7))
        labels = ("地址", "金額", "時間")
        return tuple(
            ReportTable(
                f"{table.table_id}_{index + 1}",
                f"{table.title}（{labels[index]}）",
                tuple(table.columns[position] for position in group),
                tuple(
                    tuple(row[position] for position in group)
                    for row in table.rows
                ),
                table.omitted_count,
            )
            for index, group in enumerate(groups)
        )
    if table.table_id in {"operation_stages", "holding_time"}:
        groups = (
            (tuple(range(5)), (0, 5), (0, 6), (0, 7, 8, 9))
            if table.table_id == "operation_stages"
            else (tuple(range(5)), (0, 5, 6, 7, 8, 9))
        )
        labels = ("一", "二", "三", "四")
        return tuple(
            ReportTable(
                f"{table.table_id}_{index + 1}",
                f"{table.title}（{labels[index]}）",
                tuple(table.columns[position] for position in group),
                tuple(
                    tuple(row[position] for position in group)
                    for row in table.rows
                ),
                table.omitted_count,
            )
            for index, group in enumerate(groups)
        )
    left = tuple(range(min(6, len(table.columns))))
    def part(indices, suffix, label):
        return ReportTable(
            f"{table.table_id}_{suffix}",
            f"{table.title}（{label}）",
            tuple(table.columns[index] for index in indices),
            tuple(
                tuple(row[index] for index in indices)
                for row in table.rows
            ),
            table.omitted_count,
        )

    parts = [part(left, "primary", "一")]
    labels = ("二", "三", "四", "五")
    for offset, start in enumerate(range(6, len(table.columns), 4)):
        indices = tuple(dict.fromkeys((0, 1, *range(
            start, min(start + 4, len(table.columns))
        ))))
        parts.append(part(indices, f"detail_{offset + 1}", labels[offset]))
    return tuple(parts)


def prepare_report_for_display(document):
    timezone = document.metadata.timezone or "Asia/Taipei"
    evidence = _artifact_evidence(document.evidence)
    material_assets = _material_assets(document)
    material_sources = tuple(
        dict.fromkeys(
            str(row[2])
            for section in document.sections
            for table in section.tables
            if table.table_id == "funding_sources"
            for row in table.rows
            if len(row) > 2 and str(row[1]) in material_assets
        )
    )
    material_destinations = tuple(
        dict.fromkeys(
            str(row[1])
            for section in document.sections
            for table in section.tables
            if table.table_id == "counterparty_summary"
            for row in table.rows
            if len(row) > 4
            and str(row[2]) == "流出"
            and str(row[4]) in material_assets
        )
    )
    material_counterparties = tuple(
        dict.fromkeys(
            str(row[1])
            for section in document.sections
            for table in section.tables
            if table.table_id in {"counterparty_summary", "counterparties"}
            for row in table.rows
            if len(row) > 4 and str(row[4]) in material_assets
        )
    )
    registry_rows = address_registry_rows(document)
    full_addresses = [row[2] for row in registry_rows]
    target_address = document.metadata.target_address
    address_registry = {row[2]: row[0] for row in registry_rows}
    pdf_addresses = tuple(sorted(
        dict.fromkeys(
            (
                *((target_address,) if target_address else ()),
                *material_sources[:5],
                *material_destinations[:5],
                *material_counterparties[:5],
            )
        ),
        key=lambda address: address_registry.get(address, "地址-999"),
    ))
    sections = []
    for section in document.sections:
        tables = []
        source_tables = section.tables
        content_blocks = section.content_blocks
        if section.section_id == "cover":
            content_blocks = (
                f"報告編號：{document.metadata.report_id}",
                "案件名稱：未提供",
                f"分析標的：{target_address or 'unavailable'}",
                f"鏈別：{document.metadata.chain or 'unavailable'}",
                f"分析範圍：{document.metadata.scope_type}",
                f"報告類型：{document.metadata.report_type}",
                f"版本：{document.metadata.report_version}",
                f"產製時間：{format_datetime(document.metadata.generated_at, timezone)}",
                f"資料完整度：{document.metadata.analysis_completeness}",
                f"審閱狀態：{document.metadata.review_status}",
                f"本報告時間均以 {display_timezone(timezone)} 表示。",
            )
        elif section.section_id == "evidence_index":
            source_tables = (_evidence_table(evidence),)
            content_blocks = (
                "僅列 artifact-level Evidence；record-level mapping 請參閱 report_data.json。",
            )
            section = replace(section, title="證據索引")
        elif section.section_id == "conclusion":
            content_blocks = (
                f"本次分析範圍共納入 {document.metadata.transaction_count:,} 筆交易；"
                f"主要資產為 {'、'.join(material_assets) or 'unavailable'}。"
                "已確認資料事實、規則式觀察與 AI 候選解釋均分層呈現；"
                "地址身分、控制權、交易目的及法律性質仍須外部資料與人工查證。",
            )
        elif section.section_id == "confirmed_facts":
            source_tables = (_confirmed_fact_table(document),)
            content_blocks = (
                "本節僅列由鏈上資料、Provider 與 deterministic artifact 直接支持的事實；"
                "規則結果另列於「規則式觀察」。",
            )
        elif section.section_id == "investigation_observations":
            source_tables = (*source_tables, _additional_observation_table(document))
            content_blocks = (
                "本節為 deterministic 規則式判讀，不等同鏈上直接事實或已確認身分。",
            )
        elif section.section_id.startswith("ai_") and _graph_truncated(document):
            rewritten = []
            for block in content_blocks:
                if (
                    "圖譜與供應端均未標示截斷" in block
                    or "未顯示圖譜或供應端截斷" in block
                ):
                    rewritten.append(
                        "Deterministic override：Provider 資料取得完整，但 Graph "
                        "因安全上限截斷；原 AI claim 與已確認狀態矛盾，已移除。"
                    )
                elif (
                    section.section_id == "ai_holding_time_narrative"
                    and "TRX" in block
                ):
                    rewritten.append(
                        "既有 AI 的 TRX 停留時間敘述使用隔離前資料，已標記 stale "
                        "並安全省略；USDT deterministic 結果仍以主文表格為準。"
                    )
                else:
                    rewritten.append(block)
            content_blocks = tuple(dict.fromkeys(rewritten))
        elif (
            section.section_id == "appendix"
            and full_addresses
            and not any(
                table.table_id.startswith("address_registry_")
                for table in source_tables
            )
        ):
            source_tables = (
                *(
                    table for table in source_tables
                    if table.table_id != "full_address_appendix"
                ),
                *_address_registry_tables(
                    pdf_addresses,
                    address_registry,
                    document.metadata.chain,
                ),
            )
        for raw_table in source_tables:
            if raw_table.table_id == "operation_stages":
                tables.extend(
                    _operation_stage_tables(
                        raw_table,
                        address_registry,
                        timezone,
                    )
                )
                continue
            raw_table = _material_table(
                raw_table,
                material_assets,
                material_sources,
                material_destinations,
            )
            raw_table = _format_numeric_table(raw_table)
            table = _formalize_table(raw_table)
            table = _apply_address_registry(table, address_registry)
            for part in _split_wide_table(table):
                columns = part.columns
                tables.append(
                    replace(
                        part,
                        columns=tuple(
                            format_display_text(item, timezone) for item in columns
                        ),
                        rows=tuple(
                            tuple(
                                _display_cell(value, columns[index], timezone)
                                for index, value in enumerate(row)
                            )
                            for row in part.rows
                        ),
                    )
                )
        sections.append(
            replace(
                section,
                content_blocks=tuple(
                    (
                        format_display_text(item, timezone)
                        if section.section_id == "cover"
                        else IDENTIFIER.sub(
                            lambda match: (
                                f"{abbreviate_identifier(match.group(0))}"
                                f"（{address_registry.get(match.group(0), '—')}）"
                            ),
                            format_display_text(item, timezone),
                        )
                    )
                    for item in content_blocks
                ),
                tables=tuple(tables),
            )
        )
    sections = _reorder_booklet(
        document,
        tuple(sections),
        address_registry,
        material_assets,
    )
    return replace(
        document,
        metadata=replace(
            document.metadata,
            generated_at=document.metadata.generated_at.astimezone(ZoneInfo(timezone)),
        ),
        sections=sections,
        evidence=evidence,
        conclusion=replace(
            document.conclusion,
            text=(
                f"本次分析範圍共納入 {document.metadata.transaction_count:,} 筆交易；"
                f"主要資產為 {'、'.join(material_assets) or 'unavailable'}。"
                "已確認資料事實、規則式觀察與 AI 候選解釋均分層呈現；"
                "地址身分、控制權、交易目的及法律性質仍須外部資料與人工查證。"
            ),
        ),
    )
