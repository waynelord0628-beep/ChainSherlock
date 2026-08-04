from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.reports.citations import build_citations
from crypto_investigator.reports.formatting import format_value, redact
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportFigure,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportTable,
    ReportWarning,
)


class ReportComposer:
    def compose(
        self,
        analysis,
        *,
        graph=None,
        target_address: str | None = None,
        chain: str | None = None,
        source_type: str = "file",
        source_files: tuple[str, ...] = (),
        provider_status: tuple[Mapping[str, Any], ...] = (),
        provider_errors: tuple[Mapping[str, Any], ...] = (),
        rejected_records: tuple[Mapping[str, Any], ...] = (),
        evidence: tuple[ReportEvidence, ...] = (),
        title: str = "ChainSherlock 數位資產調查報告",
        report_id: str | None = None,
        language: str = "zh-TW",
        timezone: str = "UTC",
        output_directory: str = ".",
    ) -> ReportDocument:
        data = AnalysisExporter.to_primitive(analysis)
        graph_data = AnalysisExporter.to_primitive(graph) if graph else None
        if not isinstance(data, Mapping):
            data = self._namespace_to_mapping(data)
        if graph_data is not None and not isinstance(graph_data, Mapping):
            graph_data = self._namespace_to_mapping(graph_data)
        metadata_source = data.get("metadata", {})
        completeness = str(metadata_source.get("completeness", "complete"))
        rejected_count = len(rejected_records) or int(
            metadata_source.get("rejected_record_count", 0)
        )
        warnings = tuple(
            ReportWarning("analysis_warning", redact(item))
            for item in data.get("warnings", [])
        )
        limitations = self._limitations(
            data, graph_data, completeness, provider_errors, rejected_count
        )
        sections = self._sections(
            data,
            graph_data,
            provider_status,
            provider_errors,
            rejected_records,
            evidence,
            limitations,
            completeness,
        )
        conclusion = self._conclusion(completeness, len(provider_errors), rejected_count)
        providers = tuple(
            sorted(
                {
                    str(item.get("provider"))
                    for item in provider_status
                    if item.get("provider")
                }
            )
        )
        metadata = ReportMetadata(
            report_id=report_id or f"CSR-{uuid4().hex[:12].upper()}",
            chain=chain,
            target_address=target_address,
            source_type=source_type,
            source_files=tuple(Path(item).name for item in source_files),
            providers=providers,
            analysis_completeness=completeness,
            graph_completeness=(
                str(graph_data.get("metadata", {}).get("source_completeness", completeness))
                if graph_data
                else "not_included"
            ),
            transaction_count=int(data.get("summary", {}).get("transaction_count", 0)),
            rejected_record_count=rejected_count,
            warning_count=len(warnings),
            timezone=timezone,
            language=language if language in {"zh-TW", "en-US"} else "zh-TW",
            output_directory=Path(output_directory).name or ".",
        )
        citations = build_citations(evidence, "evidence_index")
        return ReportDocument(
            title=redact(title),
            metadata=metadata,
            sections=sections,
            evidence=evidence,
            citations=citations,
            warnings=warnings,
            limitations=limitations,
            conclusion=conclusion,
        )

    @classmethod
    def _namespace_to_mapping(cls, value):
        if isinstance(value, Mapping):
            return {key: cls._namespace_to_mapping(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [cls._namespace_to_mapping(item) for item in value]
        if hasattr(value, "__dict__"):
            return {
                key: cls._namespace_to_mapping(item)
                for key, item in vars(value).items()
            }
        return AnalysisExporter.to_primitive(value)

    def _sections(
        self,
        data,
        graph,
        statuses,
        errors,
        rejected,
        evidence,
        limitations,
        completeness,
    ):
        summary = data.get("summary", {})
        statistics = data.get("statistics", {})
        counterparties = data.get("counterparties", [])[:20]
        timeline = data.get("timeline", {})
        sections = [
            ReportSection("cover", "封面", 1, ("ChainSherlock",)),
            ReportSection(
                "executive_summary",
                "執行摘要",
                2,
                (
                    f"共分析 {summary.get('transaction_count', 0)} 筆交易。",
                    f"資料完整度：{completeness}。",
                ),
            ),
            ReportSection(
                "data_sources",
                "資料來源",
                3,
                (f"證據檔案數：{len(evidence)}。",),
                evidence_refs=tuple(item.evidence_id for item in evidence),
            ),
            ReportSection(
                "target",
                "分析標的",
                3,
                (
                    f"標的：{redact(data.get('metadata', {}).get('target_address', '—'))}",
                    f"鏈別：{redact(data.get('metadata', {}).get('chain', '—'))}",
                ),
            ),
            ReportSection(
                "completeness",
                "資料完整度",
                3,
                (f"分析完整度：{completeness}。",),
            ),
            ReportSection(
                "analysis_summary",
                "分析摘要",
                4,
                tables=(
                    self._mapping_table(
                        "summary",
                        "摘要指標",
                        {
                            key: summary.get(key)
                            for key in (
                                "first_seen",
                                "last_seen",
                                "transaction_count",
                                "incoming_count",
                                "outgoing_count",
                                "unique_counterparties",
                                "active_days",
                                "unconfirmed_count",
                                "missing_timestamp_count",
                            )
                        },
                    ),
                ),
            ),
            ReportSection(
                "asset_flows",
                "資產流向",
                5,
                tables=(
                    self._asset_table(
                        statistics.get("incoming_amount", {}),
                        statistics.get("outgoing_amount", {}),
                    ),
                ),
            ),
        ]
        if counterparties:
            sections.append(
                ReportSection(
                    "counterparties",
                    "主要交易對手",
                    6,
                    tables=(self._counterparty_table(counterparties),),
                )
            )
        if timeline.get("daily") or timeline.get("monthly"):
            sections.append(
                ReportSection(
                    "timeline",
                    "時間軸",
                    7,
                    (
                        f"每日區間數：{len(timeline.get('daily', {}))}；"
                        f"每月區間數：{len(timeline.get('monthly', {}))}。",
                    ),
                )
            )
        if graph:
            gm = graph.get("metadata", {})
            sections.append(
                ReportSection(
                    "graph",
                    "交易關係圖",
                    8,
                    (
                        f"節點：{gm.get('included_node_count', len(graph.get('nodes', [])))}；"
                        f"邊：{gm.get('included_edge_count', len(graph.get('edges', [])))}；"
                        f"截斷：{gm.get('truncated', False)}。",
                    ),
                    figures=(
                        ReportFigure(
                            "F1", "互動式交易關係圖", "flow.html", "離線 HTML 圖"
                        ),
                    ),
                )
            )
        if statuses:
            sections.append(
                ReportSection(
                    "provider_status",
                    "Provider 狀態",
                    9,
                    tables=(self._records_table("providers", "Provider 狀態", statuses[:100]),),
                )
            )
        if errors:
            sections.append(
                ReportSection(
                    "provider_errors",
                    "Provider 錯誤",
                    10,
                    tables=(self._records_table("provider_errors", "Provider 錯誤", errors[:100]),),
                )
            )
        if rejected:
            sections.append(
                ReportSection(
                    "rejected_records",
                    "拒絕紀錄",
                    11,
                    (
                        f"拒絕筆數：{len(rejected)}。僅列出最多 50 筆安全摘要。",
                    ),
                    tables=(self._records_table("rejected", "拒絕原因", rejected[:50]),),
                )
            )
        sections.extend(
            (
                ReportSection("observations", "客觀觀察", 12, ("本節僅描述資料中的可驗證模式，不進行犯罪、風險或身分推論。",)),
                ReportSection("limitations", "資料限制", 13, tuple(item.description for item in limitations), limitations=limitations),
                ReportSection("conclusion", "結論", 14, (self._conclusion(completeness, len(errors), len(rejected)).text,)),
                ReportSection(
                    "evidence_index",
                    "Evidence Index",
                    15,
                    tuple(
                        f"[{item.evidence_id}] {item.source} — {item.hash or 'hash unavailable'}"
                        for item in evidence
                    )
                    or ("沒有可用的證據檔案。",),
                    evidence_refs=tuple(item.evidence_id for item in evidence),
                ),
                ReportSection(
                    "appendix",
                    "附錄",
                    16,
                    ("完整結構化資料請參閱 report_data.json。",),
                ),
            )
        )
        return tuple(sorted(sections, key=lambda item: (item.order, item.section_id)))

    @staticmethod
    def _limitations(data, graph, completeness, errors, rejected_count):
        values = [
            ReportLimitation("no_risk_assessment", "本報告不提供 AML、犯罪、風險或法律判定。"),
            ReportLimitation("no_identity_attribution", "未知地址未進行 KYC、IP、地理位置或實體身分推論。"),
        ]
        if completeness != "complete":
            values.append(ReportLimitation("partial_data", f"來源資料完整度為 {completeness}。"))
        if errors:
            values.append(ReportLimitation("provider_errors", f"存在 {len(errors)} 項 Provider 錯誤。"))
        if rejected_count:
            values.append(ReportLimitation("rejected_records", f"有 {rejected_count} 筆資料被拒絕。"))
        missing = data.get("metadata", {}).get("missing_timestamp_count", 0)
        if missing:
            values.append(ReportLimitation("missing_timestamp", f"{missing} 筆交易缺少 timestamp，未納入時間軸。"))
        if graph and graph.get("metadata", {}).get("truncated"):
            values.append(ReportLimitation("graph_truncated", "Graph 已依安全上限截斷。"))
        return tuple(values)

    @staticmethod
    def _conclusion(completeness, error_count, rejected_count):
        if completeness == "failed":
            text = "資料處理未形成足夠的有效交易結果；本報告僅記錄可驗證的失敗狀態與限制。"
        elif completeness == "partial":
            text = "本報告依部分資料產生；結果可供初步調查，但必須連同缺漏、Provider 錯誤與拒絕紀錄解讀。"
        else:
            text = "本報告已依目前取得的完整資料產生；內容僅為交易資料的描述性整理，不代表犯罪、風險或身分判定。"
        return ReportConclusion(completeness, text)

    @staticmethod
    def _mapping_table(table_id, title, values):
        return ReportTable(
            table_id,
            title,
            ("指標", "值"),
            tuple((str(key), format_value(value)) for key, value in values.items()),
        )

    @staticmethod
    def _asset_table(incoming, outgoing):
        assets = sorted(set(incoming) | set(outgoing))
        return ReportTable(
            "asset_flows",
            "依資產分離之流入／流出",
            ("資產", "流入", "流出"),
            tuple(
                (asset, format_value(incoming.get(asset, 0)), format_value(outgoing.get(asset, 0)))
                for asset in assets
            ),
        )

    @staticmethod
    def _counterparty_table(records):
        columns = ("address", "incoming_count", "outgoing_count", "interaction_count", "first_seen", "last_seen", "direction")
        return ReportTable(
            "counterparties",
            "Top 20 Counterparties",
            columns,
            tuple(tuple(format_value(item.get(column)) for column in columns) for item in records),
        )

    @staticmethod
    def _records_table(table_id, title, records):
        keys = tuple(
            sorted(
                {
                    key
                    for item in records
                    for key in item
                    if key not in {"raw", "metadata"}
                }
            )
        )
        return ReportTable(
            table_id,
            title,
            keys,
            tuple(tuple(format_value(item.get(key)) for key in keys) for item in records),
        )
