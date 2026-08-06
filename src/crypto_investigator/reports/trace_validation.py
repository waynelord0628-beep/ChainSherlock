"""Human-readable and technical dossiers for validated multi-hop traces."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Iterable

from crypto_investigator.domain.fund_tracing import TraceResult
from crypto_investigator.domain.investigation_priority import InvestigationPriority
from crypto_investigator.domain.trace_accounting import (
    BranchConservation,
    PathAllocation,
    PathAllocationType,
)
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)


def compose_trace_validation_casebook(
    result: TraceResult,
    *,
    conservation: Iterable[BranchConservation],
    priorities: Iterable[InvestigationPriority],
    allocations: Iterable[PathAllocation] = (),
    full_technical_appendix: bool = False,
) -> ReportDocument:
    """Compose one self-contained casebook with a bounded internal appendix."""

    branch_items = tuple(conservation)
    priority_items = tuple(priorities)
    allocation_items = tuple(allocations)
    sections = _casebook_sections(
        result,
        branch_items,
        priority_items,
        allocation_items,
        full_technical_appendix=full_technical_appendix,
    )
    limitations = (
        ReportLimitation(
            "TRACE-LIMIT-001",
            "FIFO 為分析配置方法，不代表鏈上可直接證明同一筆資金的逐筆身分。",
        ),
        ReportLimitation(
            "TRACE-LIMIT-002",
            "共享上限與瓶頸上限僅供路徑可能性評估，不計入可歸屬總額。",
        ),
    )
    warnings = tuple(
        ReportWarning(
            "TRACE-CONSERVATION-FAILED",
            "至少一個第一層分支尚未通過資金守恆，相關金額不得作為確定總額。",
        )
        for _ in [0]
        if any(not item.conserved for item in branch_items)
    )
    return _document(
        result,
        title="ChainSherlock 多層資金追查案件冊",
        report_type="deterministic_multihop_casebook",
        sections=sections,
        warnings=warnings,
        limitations=limitations,
        conclusion=(
            "本報告以可驗證交易邊、分支資金守恆及停止條件呈現追查結果；"
            "候選服務端點與下車點仍須以標籤來源、KYC 或其他外部證據核實。"
        ),
    )


# Backward-compatible import name; V8 now returns one self-contained casebook.
compose_trace_validation_dossiers = compose_trace_validation_casebook


def _casebook_sections(
    result: TraceResult,
    conservation: tuple[BranchConservation, ...],
    priorities: tuple[InvestigationPriority, ...],
    allocations: tuple[PathAllocation, ...],
    *,
    full_technical_appendix: bool,
) -> tuple[ReportSection, ...]:
    total = sum((item.first_hop_received for item in conservation), Decimal("0"))
    unique = sum((item.allocated_unique for item in conservation), Decimal("0"))
    unclassified = sum((item.unclassified for item in conservation), Decimal("0"))
    provider_unresolved = sum(
        (item.provider_unresolved for item in conservation), Decimal("0")
    )
    accounted = sum((item.accounted_total for item in conservation), Decimal("0"))
    shared_groups = {
        item.shared_group_id
        for item in allocations
        if item.allocation_type is PathAllocationType.SHARED_CAP
        and item.shared_group_id
    }
    shared_paths = sum(
        item.allocation_type is PathAllocationType.SHARED_CAP for item in allocations
    )
    p1 = tuple(item for item in priorities if item.tier.value == "P1")
    p2 = tuple(item for item in priorities if item.tier.value == "P2")
    confirmed = tuple(
        item
        for item in result.off_ramp_candidates
        if item.label and item.confidence >= Decimal("0.9")
    )
    provider_stops = tuple(
        item
        for item in result.stop_conditions
        if item.condition.value == "provider_incomplete"
    )
    unique_ratio = _ratio(unique, total)
    unclassified_ratio = _ratio(unclassified, total)
    conservation_ratio = _ratio(accounted, total)
    path_limit = len(result.edges) if full_technical_appendix else 30
    ranked_edges = tuple(
        sorted(
            result.edges,
            key=lambda item: (-item.amount, item.timestamp, item.edge_id),
        )[:path_limit]
    )
    main = (
        ReportSection(
            "cover",
            "ChainSherlock 多層資金追查案件冊",
            1,
            (
                f"案件編號：{result.run_id}",
                f"調查標的：{result.seed.value}",
                f"鏈別：{result.seed.chain.upper()}",
                f"追查資產：{'、'.join(result.scope.asset_filters)}",
            ),
        ),
        ReportSection(
            "casebook_contents",
            "目錄",
            2,
            (
                "第一部　調查研判正文",
                "第二部　技術驗證附錄",
                "PDF、DOCX 與 HTML 均依下列章節順序呈現；PDF 可使用書籤直接跳轉。",
            ),
        ),
        ReportSection(
            "how_to_read",
            "如何閱讀本報告",
            3,
            (
                "先閱讀執行摘要與第一層資金分布，再依 P1 任務卡查閱同一文件後段的技術證據 ID。",
                "唯一可歸屬金額可納入合計；共用資金上限只表示多條路徑共同可用的最高金額，不得重複加總。",
                "Provider（資料供應服務）未完整代表該分支資料尚未取完，不代表沒有後續活動。",
                "候選端點不等於已確認交易所、服務商、下車點或實際控制人。",
            ),
        ),
        ReportSection(
            "executive_summary",
            "執行摘要",
            4,
            (
                f"第一層總流出金額：{_amount(total)}。",
                f"帳務守恆率：{conservation_ratio}；唯一可歸屬：{_amount(unique)}（{unique_ratio}）。",
                f"尚未分類：{_amount(unclassified)}（{unclassified_ratio}）；Provider 未解決：{_amount(provider_unresolved)}。",
                f"共用資金群組 {len(shared_groups):,} 組，涉及 {shared_paths:,} 條路徑；P1 候選 {len(p1):,} 個。",
                f"已驗證標籤 {len(confirmed):,} 個；已確認下車點 {len(confirmed):,} 個。"
                "此數量僅採可信標籤且達確認門檻者。",
            ),
            evidence_refs=tuple(item.branch_id for item in conservation),
        ),
        ReportSection(
            "first_hop_distribution",
            "第一層資金分布",
            5,
            ("每個第一層分支獨立核對收到、歸屬與未解決金額。",),
            (
                ReportTable(
                    "first-hop-summary",
                    "第一層主要分支",
                    ("分支證據 ID", "資產", "收到金額", "唯一可歸屬", "未分類", "Provider 未解決", "守恆"),
                    tuple(
                        (
                            item.branch_id,
                            item.asset,
                            _amount(item.first_hop_received),
                            _amount(item.allocated_unique),
                            _amount(item.unclassified),
                            _amount(item.provider_unresolved),
                            "通過" if item.conserved else "待釐清",
                        )
                        for item in conservation
                    ),
                ),
            ),
        ),
        ReportSection(
            "multihop_overview",
            "多層分流概覽",
            6,
            (
                f"已追查至第 {max((node.hop for node in result.nodes), default=0)} 層，"
                f"建立 {len(result.edges):,} 條具交易雜湊的接觸關係。",
                f"共享上限涉及 {shared_paths:,} 條路徑；完整配置見 ALLOC-GROUP 對照與 allocation_groups.csv。",
            ),
        ),
        ReportSection(
            "attribution_summary",
            "資金歸屬與未分類摘要",
            7,
            (
                f"唯一可歸屬 { _amount(unique) }（{unique_ratio}），可直接計入歸屬合計。",
                f"尚未分類 { _amount(unclassified) }（{unclassified_ratio}），不得推定去向。",
                f"Provider 未解決 { _amount(provider_unresolved) }，相關分支保留續查狀態。",
            ),
        ),
        _priority_section("p1_tasks", "P1 調查任務", 8, p1),
        ReportSection(
            "known_labels",
            "已知標籤與服務候選",
            9,
            (
                f"目前具可信標籤並達確認門檻者 {len(confirmed):,} 個；"
                "其餘端點維持候選，不升級為已確認下車點。",
            ),
            (
                ReportTable(
                    "verified-service-labels",
                    "已驗證標籤",
                    ("地址", "標籤", "來源", "資產", "金額", "Evidence"),
                    tuple(
                        (
                            item.address,
                            item.label or "未標註",
                            item.label_source or "未保存",
                            item.asset,
                            _amount(item.received_amount),
                            "、".join(item.evidence_refs),
                        )
                        for item in confirmed
                    ),
                ),
            ),
        ),
        ReportSection(
            "unresolved_branches",
            "未解決分支",
            10,
            (
                f"Provider 未完整分支 {len(provider_stops):,} 條；未解決金額 {_amount(provider_unresolved)}。",
                "應從 checkpoint 續抓，不得把資料未完整解讀為資金已停止。",
            ),
            evidence_refs=tuple(
                ref for item in provider_stops for ref in item.evidence_refs
            ),
        ),
        ReportSection(
            "investigative_answers",
            "調查問題與目前答案",
            11,
            (
                f"目前可唯一歸屬多少？{_amount(unique)}（{unique_ratio}）。",
                f"多少仍無法分類？{_amount(unclassified)}（{unclassified_ratio}）。",
                f"是否已確認下車點？目前 {len(confirmed):,} 個端點符合可信標籤確認門檻。",
                "其餘分支仍須續追、核對標籤或依法調閱 KYC 資料。",
            ),
        ),
        ReportSection(
            "conclusion",
            "綜合研判",
            12,
            (
                "目前已建立可由交易雜湊回查的多層接觸關係，並將唯一歸屬、共享上限、"
                "未分類與 Provider 未解決金額分開呈現。",
                "候選排序反映查證效益，不代表犯罪風險、實體身分或最終受益人已獲確認。",
            ),
        ),
        ReportSection(
            "next_steps",
            "後續調查順序",
            13,
            (
                "1. 先完成 P1 分支的 Provider 續抓及交易雜湊核對。",
                "2. 查核高額端點的可信標籤、服務類型與司法管轄。",
                "3. 對共享群組執行逐筆時間與金額對帳，避免重複歸屬。",
                "4. 僅在取得可信標籤或正式調閱資料後，提出 KYC、凍結或扣押建議。",
            ),
        ),
        ReportSection(
            "evidence_index",
            "Evidence Index",
            14,
            (
                "正文引用可在本文件第二部及外部 CSV／JSON 以相同 ID 查回。",
            ),
            (
                ReportTable(
                    "casebook-evidence-index",
                    "技術證據索引",
                    ("證據類型", "ID／檔案", "用途"),
                    (
                        ("分支守恆", "分支 ID", "對應第一層收到、歸屬及未解決金額"),
                        ("候選", "CAND-*", "對應 P1／P2 候選排序"),
                        ("配置群組", "ALLOC-GROUP-*", "對應共享資金上限"),
                        ("路徑", "PATH／Edge ID", "對應交易雜湊與多層路徑"),
                        ("外部資料", "all_paths.csv／trace_graph.json", "保存完整路徑與圖譜"),
                    ),
                ),
            ),
        ),
    )
    technical = (
        ReportSection(
            "technical_appendix",
            "第二部　技術驗證附錄",
            15,
            (
                "本附錄供查核正文結論。預設僅列第一層完整守恆、P1／P2、前 30 條主要交易邊、"
                "Provider 未完整分支、共享群組及稽核摘要；完整資料保留於 CSV／JSON。",
            ),
        ),
        _technical_conservation_section(conservation, 16),
        _priority_section("technical_priorities", "P1／P2 候選明細", 17, p1 + p2),
        _technical_paths_section(ranked_edges, len(result.edges), 18),
        _provider_section(provider_stops, 19),
        _shared_group_section(allocations, 20),
        ReportSection(
            "audit_summary",
            "稽核摘要",
            21,
            (
                f"追查執行狀態：{result.status.value}。",
                f"交易邊 {len(result.edges):,} 條；停止條件 {len(result.stop_conditions):,} 筆；"
                f"Provider 未完整 {len(provider_stops):,} 筆。",
                "完整稽核事件另存 trace_audit.json；本案件冊不保存 API Key、Authorization Header 或完整請求內容。",
            ),
        ),
    )
    return main + technical


def _priority_section(
    section_id: str,
    title: str,
    order: int,
    priorities: tuple[InvestigationPriority, ...],
) -> ReportSection:
    return ReportSection(
        section_id,
        title,
        order,
        (
            "每項候選均附技術證據 ID；優先級表示查證順序，不是犯罪或風險評分。",
        ),
        (
            ReportTable(
                f"{section_id}-table",
                title,
                ("候選 ID", "地址", "資產", "級別", "分數", "優先理由", "下一步"),
                tuple(
                    (
                        item.candidate_id,
                        item.address,
                        item.asset,
                        item.tier.value,
                        str(item.score),
                        "；".join(item.priority_reasons),
                        item.required_next_action,
                    )
                    for item in priorities
                ),
            ),
        ),
        evidence_refs=tuple(item.candidate_id for item in priorities),
    )


def _technical_conservation_section(
    conservation: tuple[BranchConservation, ...], order: int
) -> ReportSection:
    return ReportSection(
        "technical_conservation",
        "第一層守恆明細",
        order,
        tables=(
            ReportTable(
                "technical-conservation",
                "完整分支守恆表",
                (
                    "分支",
                    "收到",
                    "唯一歸屬",
                    "剪枝／留存",
                    "門檻排除",
                    "Provider 未解決",
                    "未分類",
                    "共享上限",
                    "差額",
                    "狀態",
                ),
                tuple(
                    (
                        item.branch_id,
                        _amount(item.first_hop_received),
                        _amount(item.allocated_unique),
                        _amount(item.pruned + item.retained),
                        _amount(item.below_threshold),
                        _amount(item.provider_unresolved),
                        _amount(item.unclassified),
                        _amount(item.shared_cap_total),
                        _amount(item.delta),
                        "通過" if item.conserved else "待釐清",
                    )
                    for item in conservation
                ),
            ),
        ),
        evidence_refs=tuple(item.branch_id for item in conservation),
    )


def _technical_paths_section(
    edges: tuple, total_edges: int, order: int
) -> ReportSection:
    return ReportSection(
        "technical_paths",
        "主要路徑明細",
        order,
        (
            "預設依金額列出前 30 條交易邊；全部路徑及交易雜湊保留於 all_paths.csv 與 trace_graph.json。",
        ),
        (
            ReportTable(
                "technical-paths",
                "主要交易邊",
                ("Edge ID", "來源", "去向", "資產", "金額", "時間", "TxID"),
                tuple(
                    (
                        edge.edge_id,
                        edge.from_address,
                        edge.to_address,
                        edge.asset,
                        _amount(edge.amount),
                        edge.timestamp.isoformat(),
                        edge.transaction_hash,
                    )
                    for edge in edges
                ),
                omitted_count=max(0, total_edges - len(edges)),
            ),
        ),
        evidence_refs=tuple(edge.edge_id for edge in edges),
    )


def _provider_section(stops: tuple, order: int) -> ReportSection:
    return ReportSection(
        "provider_incomplete",
        "Provider 不完整",
        order,
        (
            "Provider 未完整表示資料供應服務尚未回傳完該分支，不代表地址沒有後續活動。",
        ),
        (
            ReportTable(
                "provider-incomplete-table",
                "未完整分支",
                ("狀態", "原因", "Evidence"),
                tuple(
                    (
                        "資料未完整",
                        item.reason,
                        "、".join(item.evidence_refs),
                    )
                    for item in stops
                ),
            ),
        ),
        evidence_refs=tuple(ref for item in stops for ref in item.evidence_refs),
    )


def _shared_group_section(
    allocations: tuple[PathAllocation, ...], order: int
) -> ReportSection:
    groups: dict[str, list[PathAllocation]] = {}
    for item in allocations:
        if (
            item.allocation_type is PathAllocationType.SHARED_CAP
            and item.shared_group_id
        ):
            groups.setdefault(item.shared_group_id, []).append(item)
    rows = tuple(
        (
            group_id,
            f"{len(items):,}",
            _amount(max(item.shared_cap or Decimal("0") for item in items)),
            "、".join(item.path_id for item in items[:5])
            + (f"；另有 {len(items) - 5} 條" if len(items) > 5 else ""),
        )
        for group_id, items in sorted(groups.items())
    )
    return ReportSection(
        "shared_allocations",
        "共享資金群組摘要",
        order,
        (
            "同一共享群組內的路徑共同使用一個金額上限，不得將各路徑上限重複加總。",
        ),
        (
            ReportTable(
                "shared-allocation-groups",
                "共享群組",
                ("ALLOC-GROUP ID", "涉及路徑數", "共享上限", "PATH ID"),
                rows,
            ),
        ),
        evidence_refs=tuple(groups),
    )


def _main_sections(
    result: TraceResult,
    conservation: tuple[BranchConservation, ...],
    priorities: tuple[InvestigationPriority, ...],
) -> tuple[ReportSection, ...]:
    p1 = tuple(item for item in priorities if item.tier.value == "P1")[:20]
    return (
        ReportSection(
            "cover",
            "多層資金追查調查報告",
            1,
            (
                f"調查標的：{result.seed.value}",
                f"鏈別：{result.seed.chain.upper()}",
                f"資產：{'、'.join(result.scope.asset_filters)}",
                f"追查方向：{result.scope.direction.value}",
                f"最大層數：{result.scope.max_depth}",
            ),
        ),
        ReportSection(
            "how_to_read",
            "如何閱讀本報告",
            2,
            (
                "先閱讀第一層分支守恆，再檢視 P1 調查任務卡與終止原因。",
                "可歸屬金額可納入合計；共享上限與瓶頸上限不得重複加總。",
                "候選端點不等於已確認交易所、服務商或實際控制人。",
            ),
        ),
        ReportSection(
            "branch_conservation",
            "第一層分支資金守恆",
            3,
            (
                "每個分支獨立核對收到金額、已配置、剪枝、留存、門檻排除、"
                "Provider 未解決及未分類金額。",
            ),
            (
                ReportTable(
                    "branch-conservation",
                    "第一層分支守恆摘要",
                    (
                        "分支",
                        "資產",
                        "第一層收到",
                        "可歸屬",
                        "未解決",
                        "差額",
                        "狀態",
                    ),
                    tuple(
                        (
                            item.branch_id,
                            item.asset,
                            _amount(item.first_hop_received),
                            _amount(item.allocated_unique),
                            _amount(item.unresolved_amount),
                            _amount(item.delta),
                            "通過" if item.conserved else "待釐清",
                        )
                        for item in conservation
                    ),
                ),
            ),
        ),
        ReportSection(
            "priority_tasks",
            "P1 優先調查任務",
            4,
            (
                "排序反映調查價值與證據品質，不代表風險、犯罪或身分已獲確認。",
            ),
            (
                ReportTable(
                    "p1-priority-tasks",
                    "P1 調查任務卡",
                    (
                        "候選",
                        "地址",
                        "資產",
                        "分數",
                        "優先理由",
                        "下一步",
                        "限制",
                    ),
                    tuple(
                        (
                            item.candidate_id,
                            item.address,
                            item.asset,
                            str(item.score),
                            "；".join(item.priority_reasons),
                            item.required_next_action,
                            "；".join(item.limitations) or "無額外限制",
                        )
                        for item in p1
                    ),
                    omitted_count=max(0, len(priorities) - len(p1)),
                ),
            ),
        ),
        ReportSection(
            "investigative_answers",
            "調查問題與目前答案",
            5,
            (
                f"已建立 {len(result.edges):,} 條具交易雜湊的資金邊，"
                f"涵蓋 {len(result.nodes):,} 個節點。",
                f"目前列出 {len(result.off_ramp_candidates):,} 個終端或服務端點候選，"
                "其身分均須另行核實。",
                "Provider 未完整、最大層數、重要性門檻及金額不可用等情況，"
                "均以停止條件或限制揭露，不視為已追查完成。",
            ),
        ),
        ReportSection(
            "limitations",
            "資料限制與待查證事項",
            6,
            tuple(dict.fromkeys((*result.limitations, "候選結果不得作為犯罪定性或實體身分確認。"))),
        ),
    )


def _technical_sections(
    result: TraceResult,
    conservation: tuple[BranchConservation, ...],
    priorities: tuple[InvestigationPriority, ...],
) -> tuple[ReportSection, ...]:
    return (
        ReportSection(
            "technical_scope",
            "追查範圍與安全上限",
            1,
            (
                f"Scope：{result.scope.scope_type}",
                f"最大層數：{result.scope.max_depth}",
                f"最大節點：{result.scope.max_nodes}",
                f"最大紀錄：{result.scope.max_records}",
                f"每節點最大邊數：{result.scope.max_edges_per_node}",
            ),
        ),
        ReportSection(
            "technical_conservation",
            "完整資金守恆稽核",
            2,
            tables=(
                ReportTable(
                    "technical-conservation",
                    "分支守恆欄位",
                    (
                        "分支",
                        "第一層收到",
                        "可歸屬",
                        "剪枝",
                        "留存",
                        "門檻排除",
                        "Provider 未解決",
                        "未分類",
                        "共享上限",
                        "差額",
                    ),
                    tuple(
                        (
                            item.branch_id,
                            _amount(item.first_hop_received),
                            _amount(item.allocated_unique),
                            _amount(item.pruned),
                            _amount(item.retained),
                            _amount(item.below_threshold),
                            _amount(item.provider_unresolved),
                            _amount(item.unclassified),
                            _amount(item.shared_cap_total),
                            _amount(item.delta),
                        )
                        for item in conservation
                    ),
                ),
            ),
        ),
        ReportSection(
            "technical_paths",
            "完整交易路徑",
            3,
            (
                "每一列均保留真實交易雜湊；完整資料亦輸出至 all_paths.csv。",
            ),
            (
                ReportTable(
                    "technical-paths",
                    "全部交易邊",
                    ("邊 ID", "來源", "去向", "資產", "金額", "時間", "TxID"),
                    tuple(
                        (
                            edge.edge_id,
                            edge.from_address,
                            edge.to_address,
                            edge.asset,
                            _amount(edge.amount),
                            edge.timestamp.isoformat(),
                            edge.transaction_hash,
                        )
                        for edge in result.edges
                    ),
                ),
            ),
        ),
        ReportSection(
            "technical_priorities",
            "完整候選優先級",
            4,
            tables=(
                ReportTable(
                    "technical-priorities",
                    "P1 至 P4 候選",
                    ("候選", "地址", "資產", "級別", "分數", "理由", "限制"),
                    tuple(
                        (
                            item.candidate_id,
                            item.address,
                            item.asset,
                            item.tier.value,
                            str(item.score),
                            "；".join(item.priority_reasons),
                            "；".join(item.limitations),
                        )
                        for item in priorities
                    ),
                ),
            ),
        ),
    )


def _document(
    result: TraceResult,
    *,
    title: str,
    report_type: str,
    sections: tuple[ReportSection, ...],
    warnings: tuple[ReportWarning, ...],
    limitations: tuple[ReportLimitation, ...],
    conclusion: str,
) -> ReportDocument:
    return ReportDocument(
        title=title,
        metadata=ReportMetadata(
            report_id=result.run_id,
            generated_at=datetime.now(UTC),
            report_version="8-trace-validation-1",
            chain=result.seed.chain,
            target_address=result.seed.value,
            source_type="trace_result",
            analysis_completeness=result.status.value,
            transaction_count=len(result.edges),
            timezone=result.scope.timezone,
            scope_type=result.scope.scope_type,
            scope_assets=result.scope.asset_filters,
            investigation_edge_count=len(result.edges),
            graph_node_count=len(result.nodes),
            graph_edge_count=len(result.edges),
            report_type=report_type,
            off_ramp_analysis_available=bool(result.off_ramp_candidates),
            deterministic_section_count=len(sections),
        ),
        sections=sections,
        evidence=(),
        citations=(),
        warnings=warnings,
        limitations=limitations,
        conclusion=ReportConclusion(
            completeness=result.status.value,
            text=conclusion,
        ),
    )


def _amount(value: Decimal) -> str:
    return f"{value:,.8f}".rstrip("0").rstrip(".")


def _ratio(value: Decimal, total: Decimal) -> str:
    if total == 0:
        return "0.00%"
    return f"{(value / total * Decimal('100')):.2f}%"
