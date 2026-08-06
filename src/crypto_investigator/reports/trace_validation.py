"""Human-readable and technical dossiers for validated multi-hop traces."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Iterable

from crypto_investigator.domain.fund_tracing import TraceResult
from crypto_investigator.domain.investigation_priority import InvestigationPriority
from crypto_investigator.domain.trace_accounting import BranchConservation
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)


def compose_trace_validation_dossiers(
    result: TraceResult,
    *,
    conservation: Iterable[BranchConservation],
    priorities: Iterable[InvestigationPriority],
) -> tuple[ReportDocument, ReportDocument]:
    branch_items = tuple(conservation)
    priority_items = tuple(priorities)
    main_sections = _main_sections(result, branch_items, priority_items)
    technical_sections = _technical_sections(result, branch_items, priority_items)
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
    main = _document(
        result,
        title="ChainSherlock 多層資金追查調查報告",
        report_type="deterministic_multihop_investigation",
        sections=main_sections,
        warnings=warnings,
        limitations=limitations,
        conclusion=(
            "本報告以可驗證交易邊、分支資金守恆及停止條件呈現追查結果；"
            "候選服務端點與下車點仍須以標籤來源、KYC 或其他外部證據核實。"
        ),
    )
    technical = _document(
        result,
        title="ChainSherlock 多層資金追查技術附錄",
        report_type="deterministic_multihop_technical_appendix",
        sections=technical_sections,
        warnings=warnings,
        limitations=limitations,
        conclusion="本附錄保存完整交易邊、資金守恆、候選排序與限制資料，供查核及重現。",
    )
    return main, technical


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
