import ast
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import re
from zoneinfo import ZoneInfo

from crypto_investigator.reports.formatting import (
    abbreviate_identifier,
    format_amount,
    format_datetime,
    format_duration,
    format_percent,
)
from crypto_investigator.reports.models import ReportTable


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
    return text


def _display_cell(value: str, column: str, timezone: str) -> str:
    text = format_display_text(value, timezone)
    if column != "完整地址":
        text = IDENTIFIER.sub(
            lambda match: abbreviate_identifier(match.group(0)),
            text,
        )
    return text


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
        columns.insert(index, "Address ID")
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
                    decimals = 8 if asset in {"BTC", "ETH"} else 6
                    if number and abs(number) < Decimal("0.00000001"):
                        text = f"{number:.2E}"
                    else:
                        text = format_amount(number, maximum_decimals=decimals)
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
            "Address Registry（身分資料）",
            ("Address ID", "鏈別", "完整地址", "人工 Label"),
            tuple((row[0], row[1], row[2], row[3]) for row in rows),
        ),
        ReportTable(
            "address_registry_context",
            "Address Registry（調查脈絡）",
            ("Address ID", "Candidate Role", "Evidence／來源", "備註"),
            tuple((row[0], row[4], row[5], row[6]) for row in rows),
        ),
    )


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
    if table.table_id == "operation_stages" and "Evidence" in table.columns:
        return replace(
            table,
            columns=("階段", "開始時間", "結束時間", "交易筆數", "主要資產",
                     "主要來源", "主要去向", "判定依據", "信心", "資料限制"),
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
        str(row[0]) == "fixed_amounts" for row in table.rows
    ):
        values = _row_mapping(table)
        fixed = []
        try:
            parsed = ast.literal_eval(values.get("fixed_amounts", "{}"))
            for asset, amounts in sorted(parsed.items()):
                visible = "、".join(format_amount(item) for item in amounts[:8])
                if visible:
                    fixed.append(f"{asset}：{visible}")
        except (SyntaxError, ValueError):
            pass
        return ReportTable(
            table.table_id,
            "模式摘要",
            ("判讀項目", "結果"),
            (
                ("整數金額比例", format_percent(values.get("integer_amount_ratio", 0))),
                ("批次流入視窗數", values.get("batch_incoming_count", "0")),
                ("批次流出視窗數", values.get("batch_outgoing_count", "0")),
                ("主要固定金額", "；".join(fixed) or "未辨識"),
                ("資料限制", "僅反映目前分析範圍；完整精度見 report_data.json。"),
            ),
        )
    if table.table_id == "investigation_observations" and len(table.columns) > 4:
        return ReportTable(
            table.table_id,
            "規則式觀察",
            ("規則式觀察", "引用", "信心", "資料限制"),
            tuple((row[1], row[4], row[5], row[6]) for row in table.rows),
        )
    if table.table_id == "investigation_facts" and len(table.columns) > 4:
        rows = []
        for row in table.rows:
            code, value = row[0], row[1]
            if value in {"True", "False"}:
                statement = (
                    ("有" if value == "True" else "未")
                    + f"辨識到「{code.replace('_', ' ')}」。"
                )
            else:
                statement = f"{code.replace('_', ' ')}：{value}。"
            rows.append((statement, row[5], row[3], row[6]))
        return ReportTable(
            table.table_id,
            "已確認資料事實",
            ("已確認資料事實", "引用", "信心", "資料限制"),
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
    full_addresses = sorted({
        match.group(0)
        for section in document.sections
        for cell in (
            *section.content_blocks,
            *(
                value
                for table in section.tables
                for row in table.rows
                for value in row
            ),
        )
        for match in IDENTIFIER.finditer(str(cell))
    })
    target_address = document.metadata.target_address
    if target_address in full_addresses:
        full_addresses.remove(target_address)
        full_addresses.insert(0, target_address)
    address_registry = {
        address: f"ADDR-{index:03d}"
        for index, address in enumerate(full_addresses, 1)
    }
    sections = []
    for section in document.sections:
        tables = []
        source_tables = section.tables
        content_blocks = section.content_blocks
        if section.section_id == "cover":
            content_blocks = (
                "ChainSherlock",
                "區塊鏈幣流分析報告",
                f"報告編號：{document.metadata.report_id}",
                "案件名稱：未提供",
                "案件編號：未提供",
                f"分析標的：{target_address or 'unavailable'}",
                f"鏈別：{document.metadata.chain or 'unavailable'}",
                f"分析範圍：{document.metadata.scope_type}",
                f"報告類型：{document.metadata.report_type}",
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
        elif (
            section.section_id == "appendix"
            and full_addresses
            and not any(
                table.table_id.startswith("address_registry_")
                for table in source_tables
            )
        ):
            source_tables = (
                *source_tables,
                *_address_registry_tables(
                    full_addresses,
                    address_registry,
                    document.metadata.chain,
                ),
            )
        for raw_table in source_tables:
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
                                f"{address_registry.get(match.group(0), '—')} "
                                f"{abbreviate_identifier(match.group(0))}"
                            ),
                            format_display_text(item, timezone),
                        )
                    )
                    for item in content_blocks
                ),
                tables=tuple(tables),
            )
        )
    return replace(
        document,
        metadata=replace(
            document.metadata,
            generated_at=document.metadata.generated_at.astimezone(ZoneInfo(timezone)),
        ),
        sections=tuple(sections),
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
