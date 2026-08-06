"""Professional, evidence-backed multi-hop fund-tracing report composition."""

from collections import Counter, defaultdict
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

_MAIN_EDGE_LIMIT = 20
_CANDIDATE_LIMIT = 10


def compose_multihop_report(
    result: TraceResult,
    *,
    evidence: tuple[ReportEvidence, ...] = (),
) -> ReportDocument:
    """Compose the distinct multi-hop product without changing first-hop reports."""

    warnings = _warnings(result)
    sections = (
        _cover_section(result),
        _executive_section(result),
        _scope_section(result),
        _hop_summary_section(result),
        _material_edges_section(result),
        _allocation_section(result),
        _pattern_section(result),
        _off_ramp_section(result),
        _next_steps_section(result),
        _limitations_section(result),
        _technical_appendix(result),
    )
    limitation_texts = tuple(
        dict.fromkeys(
            (
                "FIFO 是可重現的分析分配方法，不代表鏈上已證明同一筆資金的實體歸屬。",
                "未具可信標籤的終端節點僅屬候選，不代表已確認交易所、服務商或最終受益人。",
                *result.limitations,
            )
        )
    )
    limitations = tuple(
        ReportLimitation(f"TRACE-LIMIT-{index:03d}", text)
        for index, text in enumerate(limitation_texts, start=1)
    )
    complete = result.status.value == "completed" and not warnings
    return ReportDocument(
        title="多層資金追蹤與下車點候選分析報告",
        metadata=ReportMetadata(
            report_id=result.run_id,
            generated_at=datetime.now(UTC),
            report_version="8-trace-2",
            chain=result.seed.chain,
            target_address=result.seed.value,
            source_type="trace_result",
            analysis_completeness="complete" if complete else "partial",
            transaction_count=len(result.edges),
            timezone=result.scope.timezone,
            language="zh-TW",
            scope_type=result.scope.scope_type,
            scope_assets=result.scope.asset_filters,
            investigation_edge_count=len(result.edges),
            graph_node_count=len({node.address for node in result.nodes}),
            graph_edge_count=len(result.edges),
            report_type="deterministic_multihop_trace",
            off_ramp_analysis_available=bool(result.off_ramp_candidates),
            deterministic_section_count=len(sections),
            evidence_reference_count=len(_refs(result)),
        ),
        sections=sections,
        evidence=evidence,
        citations=(),
        warnings=warnings,
        limitations=limitations,
        conclusion=ReportConclusion(
            completeness="complete" if complete else "partial",
            text=_conclusion(result),
        ),
    )


def _cover_section(result: TraceResult) -> ReportSection:
    assets = "、".join(result.scope.asset_filters) or "依資料辨識"
    return ReportSection(
        "cover",
        "ChainSherlock 多層資金追蹤與下車點候選分析報告",
        1,
        (
            f"報告編號：{result.run_id}",
            f"追蹤起點：{result.seed.value}",
            f"鏈別：{result.seed.chain.upper()}",
            f"方向：{_direction(result.scope.direction.value)}",
            f"最大追蹤層級：{result.scope.max_depth}",
            f"追蹤資產：{assets}",
            f"執行狀態：{_status(result.status.value)}",
            f"本報告時間均以 UTC+8（{result.scope.timezone}）表示。",
        ),
    )


def _executive_section(result: TraceResult) -> ReportSection:
    hop_counts = _hop_counts(result)
    deepest = max(hop_counts, default=0)
    candidate_count = len(result.off_ramp_candidates)
    return ReportSection(
        "executive_summary",
        "執行摘要",
        2,
        (
            (
                f"本次以調查標的為起點，依真實交易雜湊向外追蹤至第 {deepest} 層；"
                f"目前納入 {len(result.edges):,} 條具證據參照的交易邊、"
                f"{len({node.address for node in result.nodes}):,} 個地址節點及"
                f" {len(result.allocations):,} 筆 FIFO 分配切片。"
            ),
            (
                f"規則式分析辨識 {len(result.patterns):,} 項合流、分流、回流或循環候選，"
                f"並列出 {candidate_count:,} 個後續查證端點。"
                "沒有可信 Label 的端點僅代表在本次有界範圍內未觀察到後續重大流出，"
                "不得視為已確認下車點。"
            ),
            _completeness_statement(result),
        ),
    )


def _scope_section(result: TraceResult) -> ReportSection:
    rows = (
        ("追蹤起點", result.seed.value),
        ("鏈別", result.seed.chain.upper()),
        ("追蹤方向", _direction(result.scope.direction.value)),
        ("最大層級", str(result.scope.max_depth)),
        ("每節點分支上限", str(result.scope.max_edges_per_node)),
        ("節點安全上限", f"{result.scope.max_nodes:,}"),
        ("交易安全上限", f"{result.scope.max_records:,}"),
        ("重要性門檻", _amount(result.scope.min_material_amount)),
        ("資產範圍", "、".join(result.scope.asset_filters) or "依資料辨識"),
        ("資料狀態", _status(result.status.value)),
    )
    return ReportSection(
        "trace_scope",
        "調查目的、範圍與方法",
        3,
        (
            "本報告以交易級 Trace Edge 建立多層關聯，分層呈現鏈上事實、FIFO 分配結果、"
            "規則式模式及下車點候選。所有候選均保留信心與限制，不以排行拼接資金路徑。",
            "分支、節點、交易與重要性門檻屬安全控制；觸發任一上限時，報告必須標記為部分完成。",
        ),
        (ReportTable("trace-scope-table", "追蹤設定", ("項目", "內容"), rows),),
    )


def _hop_summary_section(result: TraceResult) -> ReportSection:
    edge_hops = _edge_hops(result)
    by_hop: dict[int, list] = defaultdict(list)
    for edge in result.edges:
        by_hop[edge_hops.get(edge.edge_id, 0)].append(edge)
    rows = []
    for hop, edges in sorted(by_hop.items()):
        amounts: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for edge in edges:
            amounts[edge.asset] += edge.amount
        rows.append(
            (
                f"第 {hop} 層",
                f"{len(edges):,}",
                f"{len({edge.from_address for edge in edges}):,}",
                f"{len({edge.to_address for edge in edges}):,}",
                "；".join(
                    f"{asset} {_amount(amount)}"
                    for asset, amount in sorted(amounts.items())
                ),
                "真實交易邊彙總",
            )
        )
    return ReportSection(
        "hop_summary",
        "追蹤主線與層級摘要",
        4,
        (
            "下表按交易實際所在層級彙總，不將不同資產加總；金額為各層交易邊總額，"
            "並非目標地址的餘額或已確認可追回金額。",
        ),
        (
            ReportTable(
                "hop-summary-table",
                "各層追蹤概況",
                ("層級", "交易邊", "來源地址", "去向地址", "資產與金額", "依據"),
                tuple(rows),
            ),
        ),
    )


def _material_edges_section(result: TraceResult) -> ReportSection:
    edge_hops = _edge_hops(result)
    ranked = sorted(
        result.edges,
        key=lambda edge: (
            edge_hops.get(edge.edge_id, 0),
            -edge.amount,
            edge.timestamp,
            edge.transaction_hash,
        ),
    )
    rows = tuple(
        (
            f"第 {edge_hops.get(edge.edge_id, 0)} 層",
            edge.asset,
            edge.from_address,
            edge.to_address,
            _amount(edge.amount),
            _time(edge.timestamp, result.scope.timezone),
            edge.transaction_hash,
        )
        for edge in ranked[:_MAIN_EDGE_LIMIT]
    )
    return ReportSection(
        "material_trace_edges",
        "主要交易級資金流",
        5,
        (
            f"主文依層級及金額列示前 {len(rows)} 條重要交易；每列均對應真實交易雜湊。"
            "其餘交易保留於 report_data.json，不因主文精簡而刪除。",
        ),
        (
            ReportTable(
                "material-trace-edge-table",
                "主要交易邊",
                ("層級", "資產", "來源地址", "去向地址", "金額", "時間", "交易雜湊"),
                rows,
                omitted_count=max(0, len(result.edges) - len(rows)),
            ),
        ),
        evidence_refs=_refs(result),
    )


def _allocation_section(result: TraceResult) -> ReportSection:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for item in result.allocations:
        totals[item.asset] += item.amount
    summary = tuple(
        (asset, f"{sum(1 for item in result.allocations if item.asset == asset):,}", _amount(total))
        for asset, total in sorted(totals.items())
    )
    rows = tuple(
        (
            item.asset,
            item.lot_id,
            item.outgoing_edge_id,
            _amount(item.amount),
            "FIFO",
        )
        for item in sorted(result.allocations, key=lambda item: -item.amount)[:15]
    )
    return ReportSection(
        "fifo_allocation",
        "FIFO 資金分配",
        6,
        (
            "FIFO 依時間先後將既有流入 Lot 配對至後續流出，提供一致且可重現的分析路徑；"
            "它是鑑識分配方法，不代表鏈上或法律上已證明同一筆資金的實體歸屬。",
        ),
        (
            ReportTable("fifo-summary", "FIFO 分配摘要", ("資產", "切片數", "分配金額"), summary),
            ReportTable(
                "fifo-detail",
                "主要 FIFO 分配切片",
                ("資產", "流入 Lot", "流出 Edge", "分配金額", "方法"),
                rows,
                omitted_count=max(0, len(result.allocations) - len(rows)),
            ),
        ),
    )


def _pattern_section(result: TraceResult) -> ReportSection:
    counts = Counter(item.pattern_type.value for item in result.patterns)
    summary = tuple(
        (_pattern(name), f"{count:,}", "候選")
        for name, count in sorted(counts.items())
    )
    rows = tuple(
        (
            item.finding_id,
            _pattern(item.pattern_type.value),
            item.asset,
            f"第 {item.hop} 層",
            "、".join(item.address_refs[:3])
            + (f"；另有 {len(item.address_refs) - 3} 個" if len(item.address_refs) > 3 else ""),
            _percent(item.confidence),
            "候選",
        )
        for item in result.patterns[:15]
    )
    return ReportSection(
        "flow_patterns",
        "分流、合流、回流與關聯模式",
        7,
        (
            "下列模式由固定規則產生，僅說明交易拓樸或時間關聯；"
            "不據此確認控制關係、交易目的、犯罪行為或實際受益人。",
        ),
        (
            ReportTable("pattern-summary", "模式摘要", ("模式", "項目數", "狀態"), summary),
            ReportTable(
                "pattern-detail",
                "主要規則式模式",
                ("觀察編號", "模式", "資產", "層級", "相關地址", "信心", "狀態"),
                rows,
                omitted_count=max(0, len(result.patterns) - len(rows)),
            ),
        ),
    )


def _off_ramp_section(result: TraceResult) -> ReportSection:
    confirmed = [
        item
        for item in result.off_ramp_candidates
        if item.label and item.confidence >= Decimal("0.9")
    ]
    candidates = [
        item for item in result.off_ramp_candidates if item not in confirmed
    ][:_CANDIDATE_LIMIT]
    sections = []
    if confirmed:
        sections.append(
            ReportTable(
                "labelled-service-endpoints",
                "具可信標籤的服務端點",
                ("地址", "標籤", "資產", "收款金額", "交易數", "信心"),
                tuple(
                    (
                        item.address,
                        item.label or "未提供",
                        item.asset,
                        _amount(item.received_amount),
                        f"{item.transaction_count:,}",
                        _percent(item.confidence),
                    )
                    for item in confirmed
                ),
            )
        )
    sections.append(
        ReportTable(
            "unlabelled-terminal-candidates",
            "未標籤終端候選",
            ("地址", "資產", "收款金額", "交易數", "最後收款", "信心", "狀態"),
            tuple(
                (
                    item.address,
                    item.asset,
                    _amount(item.received_amount),
                    f"{item.transaction_count:,}",
                    _time(item.last_receipt, result.scope.timezone),
                    _percent(item.confidence),
                    "尚待查證",
                )
                for item in candidates
            ),
            omitted_count=max(0, len(result.off_ramp_candidates) - len(confirmed) - len(candidates)),
        )
    )
    return ReportSection(
        "off_ramp_candidates",
        "服務端點與下車點候選",
        8,
        (
            "具可信人工、Local Label 或 Provider Label 的服務端點，才可作為較強的停止條件；"
            "本次未標籤終端候選僅表示有界追蹤內未見後續重大流出。",
            "候選地址仍須查核標籤來源、帳戶歸屬、後續層交易及可調閱資料，"
            "不得直接稱為交易所、下車點或最終受益人。",
        ),
        tuple(sections),
    )


def _next_steps_section(result: TraceResult) -> ReportSection:
    return ReportSection(
        "next_investigation_steps",
        "尚待查證與後續調查建議",
        9,
        (
            "1. 優先續追收款金額較高且尚無可信標籤的終端候選，並沿用目前 checkpoint，避免重抓已完成頁面。",
            "2. 以人工 Label、可信公開 Label 或正式調閱結果核對服務類型；未核實前維持候選語意。",
            "3. 對回流及循環候選逐筆核對交易時間、資產與交易雜湊，排除單純共同對手或資料邊界造成的假象。",
            "4. 如需提出凍結、扣押或 KYC 調閱建議，應先確認 VASP 身分、司法管轄與帳戶歸屬。",
        ),
    )


def _limitations_section(result: TraceResult) -> ReportSection:
    grouped: dict[tuple[str, bool], list] = defaultdict(list)
    for stop in result.stop_conditions:
        grouped[(stop.condition.value, stop.reached)].append(stop)
    rows = tuple(
        (
            _stop_label(condition),
            "已觸發" if reached else "未觸發",
            f"{len(items):,}",
            _stop_summary(condition),
        )
        for (condition, reached), items in sorted(grouped.items())
    )
    return ReportSection(
        "trace_limitations",
        "資料完整度與限制",
        10,
        (
            _completeness_statement(result),
            *(
                tuple(_limitation_text(item) for item in result.limitations)
                or ("未另行記錄限制；仍須依本報告的一般候選語意審慎解讀。",)
            ),
        ),
        (
            ReportTable(
                "trace-stop-table",
                "停止條件摘要",
                ("停止條件", "狀態", "次數", "說明"),
                rows,
            ),
        ),
    )


def _technical_appendix(result: TraceResult) -> ReportSection:
    rows = tuple(
        (
            edge.edge_id,
            edge.transaction_hash,
            edge.asset,
            _amount(edge.amount),
            "、".join(edge.evidence_refs),
        )
        for edge in result.edges
    )
    return ReportSection(
        "technical_appendix",
        "技術附錄：交易與證據索引",
        11,
        (
            "完整結構化 TraceResult、原始精度、全部地址與關聯欄位另存於 report_data.json；"
            "本附錄列出交易級 Edge 與證據參照，以供重算及交叉查核。",
        ),
        (
            ReportTable(
                "trace-evidence-map",
                "交易級證據對照",
                ("Edge ID", "交易雜湊", "資產", "金額", "證據參照"),
                rows,
            ),
        ),
        evidence_refs=_refs(result),
    )


def _edge_hops(result: TraceResult) -> dict[str, int]:
    tx_hops: dict[str, int] = {}
    for node in result.nodes:
        if node.transaction_hash:
            tx_hops[node.transaction_hash] = max(
                node.hop, tx_hops.get(node.transaction_hash, 0)
            )
    return {
        edge.edge_id: max(1, tx_hops.get(edge.transaction_hash, 1))
        for edge in result.edges
    }


def _hop_counts(result: TraceResult) -> Counter:
    return Counter(_edge_hops(result).values())


def _refs(result: TraceResult) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(ref for edge in result.edges for ref in edge.evidence_refs)
    )


def _warnings(result: TraceResult) -> tuple[ReportWarning, ...]:
    if result.status.value in {"partial", "cancelled", "failed"}:
        return (
            ReportWarning(
                "TRACE-INCOMPLETE",
                f"多層追蹤狀態為「{_status(result.status.value)}」；"
                "安全上限或 Provider 邊界可能使部分後續交易未納入。",
            ),
        )
    return ()


def _completeness_statement(result: TraceResult) -> str:
    if result.status.value == "completed":
        return "本次設定範圍內的追蹤已完成；仍不代表已取得每個相關地址的無界完整歷史。"
    return (
        f"本次結果為{_status(result.status.value)}：已取得內容可供查核，"
        "但不得視為完整資金路徑或完整下車點清單。"
    )


def _conclusion(result: TraceResult) -> str:
    patterns = Counter(item.pattern_type.value for item in result.patterns)
    parts = [
        f"本次以交易級證據追蹤 {len(result.edges):,} 條資金邊，"
        f"最深至第 {max(_hop_counts(result), default=0)} 層。",
    ]
    if patterns:
        parts.append(
            "規則式拓樸顯示"
            + "、".join(f"{_pattern(name)} {count} 項" for name, count in sorted(patterns.items()))
            + "；上述均屬候選觀察。"
        )
    if result.off_ramp_candidates:
        parts.append(
            f"目前列出 {len(result.off_ramp_candidates)} 個服務端點或終端候選；"
            "沒有可信標籤者尚不能確認為下車點。"
        )
    parts.append(_completeness_statement(result))
    return "".join(parts)


def _time(value: datetime, timezone: str) -> str:
    return value.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")


def _amount(value: Decimal) -> str:
    text = f"{value:,.8f}".rstrip("0").rstrip(".")
    return text or "0"


def _percent(value: Decimal) -> str:
    return f"{value * Decimal('100'):.2f}%"


def _direction(value: str) -> str:
    return {"forward": "向後追蹤", "backward": "向前溯源", "bidirectional": "雙向追蹤"}[value]


def _status(value: str) -> str:
    return {
        "planned": "已規劃",
        "running": "執行中",
        "partial": "部分完成",
        "completed": "完成",
        "cancelled": "已取消",
        "failed": "失敗",
    }[value]


def _pattern(value: str) -> str:
    return {
        "aggregation": "合流",
        "dispersion": "分流",
        "return_flow": "回流",
        "cyclic_flow": "循環",
        "shared_counterparty": "共同交易對手",
        "revenue_share_candidate": "規律分配候選",
        "off_ramp_contact": "服務端點接觸候選",
    }[value]


def _stop_label(value: str) -> str:
    return {
        "confirmed_exchange_or_vasp": "已確認交易所／VASP",
        "payment_service": "支付服務",
        "otc_candidate": "OTC 候選",
        "mixer": "混幣服務",
        "bridge": "跨鏈橋",
        "no_further_outgoing_activity": "未觀察到後續重大流出",
        "below_materiality_threshold": "低於重要性門檻",
        "max_depth_reached": "已達最大層級",
        "provider_incomplete": "Provider 資料未完整",
        "manual_stop": "人工停止",
    }[value]


def _stop_summary(value: str) -> str:
    return {
        "confirmed_exchange_or_vasp": "可信標籤支持時停止延伸。",
        "payment_service": "支付服務標籤支持時停止延伸。",
        "otc_candidate": "OTC 候選需人工查證。",
        "mixer": "混幣服務標籤支持時停止延伸。",
        "bridge": "跨鏈後需另建對應鏈追蹤。",
        "no_further_outgoing_activity": "本次有界範圍內未見重大後續流出。",
        "below_materiality_threshold": "低於設定的重要性門檻。",
        "max_depth_reached": "已達本次設定的最大追蹤層級。",
        "provider_incomplete": "Provider 分頁或查詢額度未完整。",
        "manual_stop": "依人工指定停止地址或安全控制停止。",
    }[value]


def _limitation_text(value: str) -> str:
    if value == "trongrid/token_transfers pagination incomplete":
        return "TronGrid token_transfers 分頁未完整。"
    if value.startswith("Per-node provider frontier cap "):
        parts = value.removesuffix(".").split()
        return f"第 {parts[-1]} 層觸發每節點 Provider 分支上限 {parts[4]}。"
    if value == "Configured address-query budget was reached.":
        return "已達設定的地址查詢額度上限。"
    return value
