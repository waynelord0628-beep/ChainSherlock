"""Report composition for evidence-backed multi-hop fund tracing."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from crypto_investigator.domain.fund_tracing import TraceResult
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)


def compose_multihop_report(
    result: TraceResult,
    *,
    evidence: tuple[ReportEvidence, ...] = (),
) -> ReportDocument:
    """Compose a separate multi-hop product without changing first-hop templates."""

    timezone = result.scope.timezone
    warnings = _warnings(result)
    sections = (
        _cover_section(result),
        _executive_section(result),
        _scope_section(result),
        _edge_section(result),
        _allocation_section(result),
        _pattern_section(result),
        _off_ramp_section(result),
        _limitations_section(result),
    )
    limitations = tuple(
        ReportLimitation(f"TRACE-LIMIT-{index:03d}", text)
        for index, text in enumerate(
            (
                "FIFO 為分析配對方法，不代表識別出鏈上同一筆資金。",
                "候選下車點與角色須經可信 Label 或人工證據確認。",
                *result.limitations,
            ),
            start=1,
        )
    )
    complete = result.status.value == "completed" and not warnings
    return ReportDocument(
        title="多層資金追蹤與下車點候選報告",
        metadata=ReportMetadata(
            report_id=result.run_id,
            generated_at=datetime.now(UTC),
            report_version="8-trace-1",
            chain=result.seed.chain,
            target_address=result.seed.value,
            source_type="trace_result",
            analysis_completeness="complete" if complete else "partial",
            transaction_count=len(result.edges),
            timezone=timezone,
            language="zh-TW",
            scope_type=result.scope.scope_type,
            scope_assets=result.scope.asset_filters,
            investigation_edge_count=len(result.edges),
            graph_node_count=len({node.address for node in result.nodes}),
            graph_edge_count=len(result.edges),
            report_type="deterministic_multihop_trace",
            off_ramp_analysis_available=True,
            deterministic_section_count=len(sections),
            evidence_reference_count=len(evidence),
        ),
        sections=sections,
        evidence=evidence,
        citations=(),
        warnings=warnings,
        limitations=limitations,
        conclusion=ReportConclusion(
            completeness="complete" if complete else "partial",
            text=(
                f"本次以 {result.scope.direction.value} 方向追蹤至最多 "
                f"{result.scope.max_depth} 層，共納入 {len(result.edges)} 筆具交易雜湊及"
                f"證據參照的交易邊；辨識 {len(result.patterns)} 項規則式候選與 "
                f"{len(result.off_ramp_candidates)} 個下車點候選。候選身分與最終受益人"
                "仍須另行查證。"
            ),
        ),
    )


def _scope_section(result):
    rows = (
        ("調查標的", result.seed.value),
        ("鏈別", result.seed.chain.upper()),
        ("方向", _direction(result.scope.direction.value)),
        ("最大層數", str(result.scope.max_depth)),
        ("資產", "、".join(result.scope.asset_filters) or "未限定"),
        ("重要性門檻", _amount(result.scope.min_material_amount)),
        ("狀態", _status(result.status.value)),
    )
    return ReportSection(
        "trace-scope",
        "調查目的與追蹤範圍",
        3,
        (
            "本報告僅呈現可由真實交易雜湊與 Evidence 支持的多層關係；"
            "不同資產分開追蹤。",
        ),
        (ReportTable("trace-scope-table", "追蹤設定", ("項目", "內容"), rows),),
    )


def _edge_section(result):
    rows = tuple(
        (
            edge.edge_id,
            edge.asset,
            edge.from_address,
            edge.to_address,
            _amount(edge.amount),
            _time(edge.timestamp, result.scope.timezone),
            edge.transaction_hash,
            "、".join(edge.evidence_refs),
        )
        for edge in result.edges
    )
    return ReportSection(
        "verified-trace-edges",
        "具證據支持的交易關係",
        4,
        ("每列均為實際交易，不以來源與去向排行拼接路徑。",),
        (
            ReportTable(
                "trace-edges",
                "交易關係",
                ("Edge ID", "資產", "來源", "去向", "金額", "時間"),
                tuple(row[:6] for row in rows),
            ),
            ReportTable(
                "trace-edge-evidence",
                "交易雜湊與證據對照",
                ("Edge ID", "Tx Hash", "證據"),
                tuple((row[0], row[6], row[7]) for row in rows),
            ),
        ),
        evidence_refs=_refs(result),
    )


def _allocation_section(result):
    rows = tuple(
        (
            item.allocation_id,
            item.asset,
            item.lot_id,
            item.outgoing_edge_id,
            _amount(item.amount),
            "FIFO",
        )
        for item in result.allocations
    )
    return ReportSection(
        "fifo-allocation",
        "FIFO 資金配對",
        5,
        ("FIFO 配對用於追蹤額度分配，不等同確認同一筆資金。",),
        (
            ReportTable(
                "fifo-allocation-table",
                "配對結果",
                ("配對 ID", "資產", "流入 Lot", "流出 Edge", "配對金額", "方法"),
                rows,
            ),
        ),
    )


def _pattern_section(result):
    rows = tuple(
        (
            item.finding_id,
            _pattern(item.pattern_type.value),
            item.asset,
            str(item.hop),
            "、".join(item.address_refs),
            "；".join(
                f"{_metric_label(key)}：{value}"
                for key, value in sorted(item.metrics.items())
            ),
            _percent(item.confidence),
            "候選",
        )
        for item in result.patterns
    )
    return ReportSection(
        "flow-patterns",
        "回流、集中與分散態樣",
        6,
        ("規則式結果只表示候選態樣，不確認控制關係、目的或犯罪性質。",),
        (
            ReportTable(
                "flow-pattern-table",
                "規則式候選摘要",
                ("Finding ID", "態樣", "資產", "層級", "信心", "狀態"),
                tuple((row[0], row[1], row[2], row[3], row[6], row[7]) for row in rows),
            ),
            ReportTable(
                "flow-pattern-detail",
                "候選地址與量化依據",
                ("Finding ID", "地址", "量化依據"),
                tuple((row[0], row[4], row[5]) for row in rows),
            ),
        ),
    )


def _off_ramp_section(result):
    rows = tuple(
        (
            item.address,
            item.label or "未提供",
            item.label_source or "未提供",
            item.asset,
            _amount(item.received_amount),
            str(item.transaction_count),
            _time(item.first_receipt, result.scope.timezone),
            _time(item.last_receipt, result.scope.timezone),
            _percent(item.confidence),
            "候選；須查證",
        )
        for item in result.off_ramp_candidates
    )
    return ReportSection(
        "off-ramp-candidates",
        "下車點與服務商候選",
        7,
        ("只有可信 Label 命中才能形成已驗證停止條件；行為規律本身不足以確認身分。",),
        (
            ReportTable(
                "off-ramp-table",
                "下車點候選摘要",
                (
                    "地址",
                    "Label",
                    "來源",
                    "資產",
                    "收款金額",
                    "交易數",
                    "信心",
                ),
                tuple((row[0], row[1], row[2], row[3], row[4], row[5], row[8]) for row in rows),
            ),
            ReportTable(
                "off-ramp-timing",
                "候選時間與狀態",
                ("地址", "首次", "最後", "狀態"),
                tuple((row[0], row[6], row[7], row[9]) for row in rows),
            ),
        ),
    )


def _limitations_section(result):
    rows = tuple(
        (
            stop.condition.value,
            stop.reason,
            "是" if stop.reached else "否",
            "、".join(stop.evidence_refs) or "未提供",
        )
        for stop in result.stop_conditions
    )
    return ReportSection(
        "trace-limitations",
        "停止條件與資料限制",
        8,
        tuple(result.limitations) or ("未另行提供案件限制；仍適用本報告通用限制。",),
        (
            ReportTable(
                "trace-stop-table",
                "停止條件",
                ("條件", "原因", "已觸發", "證據"),
                rows,
            ),
        ),
    )


def _warnings(result):
    if result.status.value in {"partial", "cancelled", "failed"}:
        return (
            ReportWarning(
                "TRACE-INCOMPLETE",
                f"多層追蹤狀態為 {_status(result.status.value)}，不得視為完整路徑。",
            ),
        )
    return ()


def _cover_section(result):
    return ReportSection(
        "cover",
        "ChainSherlock 多層資金追蹤與下車點候選報告",
        1,
        (
            f"報告編號：{result.run_id}",
            f"調查標的：{result.seed.value}",
            f"鏈別：{result.seed.chain.upper()}",
            f"追蹤方向：{_direction(result.scope.direction.value)}",
            f"最大層數：{result.scope.max_depth}",
            f"追蹤資產：{'、'.join(result.scope.asset_filters) or '未限定'}",
            f"報告狀態：{_status(result.status.value)}",
            f"時區：UTC+8（{result.scope.timezone}）",
        ),
    )


def _executive_section(result):
    return ReportSection(
        "executive_summary",
        "執行摘要",
        2,
        (
            f"本次從調查標的向前及／或向後追蹤最多 {result.scope.max_depth} 層，"
            f"共納入 {len(result.edges)} 筆具真實交易雜湊與 Evidence 的交易關係。",
            f"規則式分析辨識 {len(result.patterns)} 項回流、集中、分散或重複受款候選，"
            f"並列出 {len(result.off_ramp_candidates)} 個下車點／服務商候選。",
            "FIFO 僅作資金額度配對；候選角色、下車點及最終受益人均須另行查證。",
        ),
    )


def _refs(result):
    return tuple(dict.fromkeys(ref for edge in result.edges for ref in edge.evidence_refs))


def _time(value, timezone):
    return value.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")


def _amount(value: Decimal):
    text = f"{value:,.8f}".rstrip("0").rstrip(".")
    return text or "0"


def _percent(value):
    return f"{value * Decimal('100'):.2f}%"


def _direction(value):
    return {"forward": "向後追蹤", "backward": "向前溯源", "bidirectional": "雙向"}[value]


def _status(value):
    return {
        "planned": "已規劃",
        "running": "執行中",
        "partial": "部分完成",
        "completed": "完成",
        "cancelled": "已取消",
        "failed": "失敗",
    }[value]


def _pattern(value):
    return {
        "aggregation": "集中",
        "dispersion": "分散",
        "return_flow": "回流",
        "cyclic_flow": "循環",
        "shared_counterparty": "共同交易對手",
        "revenue_share_candidate": "分潤候選",
        "off_ramp_contact": "下車點接觸候選",
    }[value]


def _metric_label(value):
    return {
        "source_count": "來源地址數",
        "destination_count": "去向地址數",
        "transaction_count": "交易筆數",
        "total_amount": "總金額",
        "cycle_closing_edge_count": "循環閉合 Edge 數",
        "repeated_recipient_count": "重複受款地址數",
        "payment_count": "付款筆數",
        "repeated_amount_value_count": "重複金額種類數",
    }.get(value, value)
