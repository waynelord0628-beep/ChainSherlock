from pathlib import Path
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4
from dataclasses import replace

from crypto_investigator.analyzers.export import AnalysisExporter
from crypto_investigator.reports.citations import build_citations
from crypto_investigator.reports.ai_enrichment import AIReportIntegrator
from crypto_investigator.reports.formatting import (
    format_amount,
    format_datetime,
    format_compact,
    format_duration,
    format_percent,
    format_value,
    redact,
)
from crypto_investigator.reports.materiality import classify_assets
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
        investigation=None,
        narrative=None,
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
        materiality_thresholds: Mapping[str, Decimal] | None = None,
        include_assets: frozenset[str] = frozenset(),
        exclude_assets: frozenset[str] = frozenset(),
    ) -> ReportDocument:
        data = AnalysisExporter.to_primitive(analysis)
        graph_data = AnalysisExporter.to_primitive(graph) if graph else None
        investigation_data = (
            AnalysisExporter.to_primitive(investigation) if investigation else None
        )
        if not isinstance(data, Mapping):
            data = self._namespace_to_mapping(data)
        if graph_data is not None and not isinstance(graph_data, Mapping):
            graph_data = self._namespace_to_mapping(graph_data)
        if investigation_data is not None and not isinstance(investigation_data, Mapping):
            investigation_data = self._namespace_to_mapping(investigation_data)
        if investigation_data:
            record_ids = tuple(
                str(item.get("evidence_id"))
                for item in investigation_data.get("evidence_refs", [])
                if item.get("evidence_id")
            )
            artifact_index = next(
                (
                    index
                    for index, item in enumerate(evidence)
                    if item.source == "investigation_evidence.json"
                ),
                None,
            )
            if artifact_index is None:
                evidence = evidence + (
                    ReportEvidence(
                        evidence_id="INVESTIGATION_ARTIFACT",
                        evidence_type="investigation_artifact",
                        source="investigation_evidence.json",
                        source_reference="investigation_evidence.json",
                        description=(
                            "Deterministic investigation fact and observation records"
                        ),
                        hash=None,
                        metadata={"record_ids": record_ids},
                    ),
                )
            else:
                artifact = evidence[artifact_index]
                evidence = tuple(
                    replace(
                        item,
                        metadata={**item.metadata, "record_ids": record_ids},
                    )
                    if item.source == "investigation_evidence.json"
                    else item
                    for index, item in enumerate(evidence)
                )
        evidence = tuple(
            dict((item.evidence_id, item) for item in evidence).values()
        )
        evidence = tuple(
            replace(
                item,
                source=redact(item.source),
                source_reference=redact(item.source_reference),
                description=redact(item.description),
            )
            for item in evidence
        )
        metadata_source = data.get("metadata", {})
        completeness = str(metadata_source.get("completeness", "complete"))
        scope = metadata_source.get("analysis_scope") or {}
        time_scope = metadata_source.get("time_scope") or {}
        report_timezone = str(scope.get("timezone") or timezone)
        scope_type = str(scope.get("scope_type", "unavailable"))
        full_history_complete = bool(
            time_scope.get("full_history_complete", False)
        )
        graph_metadata = graph_data.get("metadata", {}) if graph_data else {}
        investigation_metadata = (
            investigation_data.get("structured_metadata", {})
            if investigation_data
            else {}
        )
        trc10_assets = frozenset(
            str(item)
            for item in metadata_source.get("trc10_asset_symbols", ())
        )
        asset_presentations = classify_assets(
            data.get("statistics", {}).get("incoming_amount", {}),
            data.get("statistics", {}).get("outgoing_amount", {}),
            data.get("statistics", {}).get("asset_breakdown", {}),
            materiality_thresholds=materiality_thresholds,
            include_assets=include_assets,
            exclude_assets=exclude_assets | trc10_assets,
        )
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
        if any(item.hash is None for item in evidence):
            limitations += (
                ReportLimitation(
                    "evidence_hash_unavailable",
                    "部分 Evidence artifact 無法取得 SHA-256；已保留限制且未標示為 verified。",
                ),
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
            target_address,
            chain,
            investigation_data,
            scope,
            time_scope,
            asset_presentations,
        )
        conclusion = self._conclusion(
            completeness, len(provider_errors), rejected_count, investigation_data
        )
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
            timezone=report_timezone,
            language=language if language in {"zh-TW", "en-US"} else "zh-TW",
            output_directory=Path(output_directory).name or ".",
            scope_type=scope_type,
            requested_date_from=scope.get("date_from"),
            requested_date_to=scope.get("date_to"),
            full_history_complete=full_history_complete,
            provider_raw_record_count=int(
                metadata_source.get(
                    "provider_raw_record_count",
                    data.get("summary", {}).get("transaction_count", 0),
                )
            ),
            normalized_record_count=int(
                metadata_source.get(
                    "normalized_record_count",
                    data.get("summary", {}).get("transaction_count", 0),
                )
            ),
            analysis_record_count=int(
                metadata_source.get(
                    "analysis_record_count",
                    data.get("summary", {}).get("transaction_count", 0),
                )
            ),
            investigation_edge_count=int(
                investigation_metadata.get("source_transaction_count", 0)
            ),
            graph_node_count=int(
                graph_metadata.get(
                    "included_node_count", len(graph_data.get("nodes", []))
                )
                if graph_data
                else 0
            ),
            graph_edge_count=int(
                graph_metadata.get(
                    "included_edge_count", len(graph_data.get("edges", []))
                )
                if graph_data
                else 0
            ),
            rejected_count=rejected_count,
            deduplicated_count=int(
                metadata_source.get("deduplicated_record_count", 0)
            ),
            failed_count=int(
                (investigation_data or {})
                .get("direction_reconciliation", {})
                .get("failed_transaction_count", 0)
            ),
            unclassified_count=int(
                (investigation_data or {})
                .get("direction_reconciliation", {})
                .get("unclassified_direction_count", 0)
            ),
            excluded_by_scope=int(
                metadata_source.get(
                    "excluded_by_scope",
                    time_scope.get("excluded_by_scope", 0),
                )
            ),
            deterministic_section_count=len(sections),
            evidence_reference_count=len(evidence),
        )
        citations = build_citations(evidence, "evidence_index")
        document = ReportDocument(
            title=redact(title),
            metadata=metadata,
            sections=sections,
            evidence=evidence,
            citations=citations,
            warnings=warnings,
            limitations=limitations,
            conclusion=conclusion,
        )
        if narrative is not None:
            return AIReportIntegrator().integrate(
                document,
                narrative,
                validation_source=investigation_data,
            )
        return document

    @staticmethod
    def _narrative_sections(narrative):
        if not getattr(narrative, "validation", None) or not narrative.validation.valid:
            return ()
        metadata = narrative.metadata
        fallback = bool(metadata.fallback_used)
        label = "規則式敘事" if fallback else "AI 輔助敘事"
        review = getattr(narrative.review_status, "value", narrative.review_status)
        header = (
            (
                "AI 請求失敗，已使用規則式替代敘事；"
                if fallback
                else "AI 輔助敘事；"
            )
            +
            f"provider={redact(metadata.provider)}；model={redact(metadata.model)}；"
            f"prompt={redact(metadata.prompt_version)}；validation=passed；"
            f"fallback={metadata.fallback_used}。"
        )
        if review == "not_reviewed":
            header += " AI 內容尚未經人工確認。"
        result = []
        order = 20
        names = (
            "executive_summary", "funding_narrative", "outgoing_narrative",
            "stage_narrative", "pattern_narrative", "alternative_explanations",
            "investigative_leads", "conclusion",
        )
        for name in names:
            section = getattr(narrative, name, None)
            if section:
                refs = tuple(
                    citation.evidence_id
                    for citation in narrative.citations
                    if citation.section in {name, section.section_id}
                )
                result.append(ReportSection(
                    f"ai_{name}", f"{label}：{redact(section.title)}", order,
                    ((header,) if not result else ()) + tuple(
                        redact(paragraph.text) for paragraph in section.paragraphs
                    ),
                    evidence_refs=refs,
                ))
                order += 1
        return tuple(result)

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
        target_address,
        chain,
        investigation,
        scope,
        time_scope,
        asset_presentations,
    ):
        summary = data.get("summary", {})
        statistics = data.get("statistics", {})
        counterparties = data.get("counterparties", [])[:20]
        timeline = data.get("timeline", {})
        scope_type = str(scope.get("scope_type", "unavailable"))
        full_history_complete = bool(
            time_scope.get("full_history_complete", False)
        )
        if scope_type == "custom_date_range":
            scope_description = (
                "指定分析期間："
                f"{format_datetime(scope.get('date_from'), scope.get('timezone', 'UTC'))}"
                " 至 "
                f"{format_datetime(scope.get('date_to'), scope.get('timezone', 'UTC'))}"
                f"（{scope.get('timezone', 'UTC')}）"
            )
            first_label, last_label = "期間內最早交易時間", "期間內最晚交易時間"
        elif scope_type == "full_history" and full_history_complete:
            scope_description = "依已完整取得之歷史資料。"
            first_label, last_label = "地址首次交易時間", "地址最後交易時間"
        elif scope_type == "full_history":
            scope_description = (
                "依目前已取得之部分歷史資料；不得解讀為地址完整生命週期。"
            )
            first_label, last_label = "目前資料最早時間", "目前資料最晚時間"
        elif scope_type == "quick_preview":
            scope_description = (
                "Quick Preview 僅為受限預覽，不代表完整歷史或完整總額。"
            )
            first_label, last_label = "預覽資料最早時間", "預覽資料最晚時間"
        else:
            scope_description = "分析範圍 metadata unavailable；時間語意僅限目前資料。"
            first_label, last_label = "目前資料最早時間", "目前資料最晚時間"
        pipeline = self._pipeline_counts(data, graph, investigation, time_scope)
        material_assets = tuple(item for item in asset_presentations if item.material)
        trc10_assets = frozenset(
            str(item)
            for item in data.get("metadata", {}).get("trc10_asset_symbols", ())
        )
        appendix_assets = tuple(
            item
            for item in asset_presentations
            if not item.material and item.asset not in trc10_assets
        )
        micro_excluded_count = int(
            data.get("metadata", {}).get("micro_trx_excluded_count", 0)
        )
        micro_excluded_amount = str(
            data.get("metadata", {}).get("micro_trx_excluded_amount", "0")
        )
        micro_threshold = str(
            data.get("metadata", {}).get("trx_dust_threshold", "0.0001")
        )
        micro_summary = (
            "另有低於重要性門檻之微額轉入，已保留於原始 Evidence，"
            "惟未納入主要資金流與行為模式分析。"
        )
        trc10_summary = tuple(
            data.get("metadata", {}).get("trc10_other_asset_summary", ())
        )
        sections = [
            ReportSection(
                "cover",
                "封面",
                1,
                (
                    "ChainSherlock",
                    "本報告時間均以 UTC+8（Asia/Taipei）表示。"
                    if scope.get("timezone") == "Asia/Taipei"
                    else f"本報告時間均以 {scope.get('timezone', 'timezone unknown')} 表示。",
                ),
            ),
            ReportSection(
                "executive_summary",
                "執行摘要",
                2,
                (
                    scope_description,
                    f"完整交易統計共 {summary.get('transaction_count', 0)} 筆。",
                    f"主要資金流與行為分析使用 "
                    f"{data.get('metadata', {}).get('analysis_record_count', summary.get('transaction_count', 0))} 筆。",
                    f"資料完整度：{completeness}。",
                    *((micro_summary,) if micro_excluded_count else ()),
                ),
            ),
            ReportSection(
                "target",
                "調查標的與分析範圍",
                3,
                (
                    f"標的：{redact(target_address or '—')}",
                    f"鏈別：{redact(chain or '—')}",
                    scope_description,
                ),
            ),
            ReportSection(
                "data_sources",
                "資料來源、Provider 與完整度",
                4,
                (
                    f"證據 artifact：{len(evidence)} 個。",
                    f"Provider 錯誤：{len(errors)}；被拒絕資料：{len(rejected)}。",
                ),
                evidence_refs=tuple(item.evidence_id for item in evidence),
            ),
            ReportSection(
                "completeness",
                "資料完整度",
                4,
                (
                    f"分析完整度：{completeness}。",
                    f"Provider 錯誤：{len(errors)} 筆。",
                    f"被拒絕資料：{len(rejected)} 筆。",
                ),
            ),
            ReportSection(
                "data_pipeline",
                "資料流程計數與排除",
                5,
                (
                    "各階段可能因範圍過濾、去重、正規化拒絕及 Graph 安全上限而使用不同母體。",
                ),
                tables=(pipeline,),
            ),
            ReportSection(
                "analysis_summary",
                "分析摘要",
                6,
                tables=(
                    self._mapping_table(
                        "summary",
                        "摘要指標",
                        {
                            "分析範圍": scope_description,
                            first_label: (
                                "無法確認（歷史資料不完整）"
                                if scope_type == "full_history"
                                and not full_history_complete
                                else format_datetime(
                                    summary.get("first_seen"),
                                    scope.get("timezone", "UTC"),
                                )
                            ),
                            last_label: format_datetime(
                                summary.get("last_seen"),
                                scope.get("timezone", "UTC"),
                            ),
                            "分析交易筆數": summary.get("transaction_count"),
                            "流入交易筆數": summary.get("incoming_count"),
                            "流出交易筆數": summary.get("outgoing_count"),
                            "未分類方向筆數": (
                                (investigation or {})
                                .get("direction_reconciliation", {})
                                .get("unclassified_direction_count", 0)
                            ),
                            "主要資產": tuple(item.asset for item in material_assets),
                            "主要交易對手數": summary.get("unique_counterparties"),
                            "資料完整度": completeness,
                        },
                    ),
                ),
            ),
            ReportSection(
                "asset_flows",
                "資產流向",
                7,
                (
                    "金額依資產分開列示，不跨資產加總。"
                    + (
                        " 下列為目前部分資料中的金額，不代表完整歷史總額。"
                        if completeness != "complete"
                        else ""
                    ),
                ),
                tables=(
                    self._asset_presentation_table(material_assets),
                    self._asset_time_table(
                        material_assets,
                        time_scope,
                        scope.get("timezone", "UTC"),
                    ),
                ),
            ),
            ReportSection(
                "confirmed_facts",
                "已確認資料事實",
                18,
                (
                    "本節只列結構化資料直接支持的交易數、範圍、資產與 Provider 狀態；不含角色或目的推論。",
                ),
                tables=(
                    self._mapping_table(
                        "confirmed_data_facts",
                        "Confirmed Data Facts",
                        {
                            "Analysis 交易數": summary.get("transaction_count", 0),
                            "分析鏈別": chain or "unavailable",
                            "分析範圍": scope_type,
                            "完整度": completeness,
                            "重要資產": tuple(
                                item.asset for item in material_assets
                            ),
                        },
                    ),
                ),
            ),
        ]
        if appendix_assets:
            sections.append(
                ReportSection(
                    "non_material_assets",
                    "低重要性及 Spam Candidate 項目",
                    29,
                    (
                        "本節僅列 deterministic materiality 候選；未修改或刪除原始 Evidence。"
                        "所有排除均可恢復並須人工覆核，不構成資產或發行方定性。",
                    ),
                    tables=(
                        self._asset_presentation_table(
                            appendix_assets, appendix=True
                        ),
                    ),
                )
            )
        if trc10_summary:
            class_labels = {
                "advertisement_token_candidate": "Advertisement Token Candidate",
                "spam_token_candidate": "Spam Token Candidate",
                "unknown_trc10_asset": "Unknown TRC10 Asset",
            }
            sections.append(
                ReportSection(
                    "trc10_other_assets",
                    "TRC10／其他資產轉入摘要",
                    89,
                    (
                        "下列項目均為 TransferAssetContract，未納入原生 TRX "
                        "統計、排行或行為模式；候選分類不代表已確認為詐騙或釣魚。",
                    ),
                    tables=(
                        ReportTable(
                            "trc10_other_asset_summary",
                            "TRC10／Other Asset Transfers",
                            (
                                "資產／Symbol",
                                "交易筆數",
                                "流入數量",
                                "來源地址數",
                                "候選類型",
                                "信心",
                                "人工審閱",
                            ),
                            tuple(
                                (
                                    str(item.get("symbol", "unknown_tron_asset")),
                                    str(item.get("transaction_count", 0)),
                                    format_amount(item.get("incoming_amount", 0)),
                                    str(item.get("source_address_count", 0)),
                                    class_labels.get(
                                        str(
                                            item.get(
                                                "candidate_classification",
                                                "unknown_trc10_asset",
                                            )
                                        ),
                                        "Unknown TRC10 Asset",
                                    ),
                                    str(item.get("confidence", "low")),
                                    "尚未審閱",
                                )
                                for item in trc10_summary[:10]
                            ),
                        ),
                    ),
                    section_type="technical_appendix",
                )
            )
        if micro_excluded_count:
            sections.append(
                ReportSection(
                    "dust_exclusion_summary",
                    "技術附錄：微額 TRX 排除摘要",
                    91,
                    (),
                    tables=(
                        self._mapping_table(
                            "dust_exclusion_summary",
                            "微額 TRX 排除摘要",
                            {
                                "排除筆數": micro_excluded_count,
                                "排除合計金額": micro_excluded_amount,
                                "materiality threshold": micro_threshold,
                                "exclusion rule": (
                                    "native_trx_below_materiality_threshold"
                                ),
                                "reversible": True,
                                "review status": "not_reviewed",
                            },
                        ),
                    ),
                    section_type="technical_appendix",
                )
            )
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
                        f"截斷：{'是' if gm.get('truncated', False) else '否'}。",
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
                    tables=(self._provider_table(statuses[:100]),),
                )
            )
        if investigation:
            sections.extend(
                self._investigation_sections(
                    investigation,
                    data,
                    completeness,
                    graph,
                    statuses,
                    scope.get("timezone", "UTC"),
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
                ReportSection(
                    "observations",
                    "規則式觀察",
                    18,
                    (
                        "本節僅描述資料中的可驗證模式，不進行犯罪、風險或身分推論。",
                    ),
                ),
                ReportSection(
                    "candidate_interpretations",
                    "候選解釋",
                    19,
                    (
                        "所有未由可信 Local Label 支持的角色均為 Candidate，不是 Confirmed。",
                    ),
                ),
                ReportSection(
                    "unresolved_questions",
                    "尚待查證",
                    50,
                    (
                        "交易目的、地址實際控制人及鏈下背景仍需外部證據查證。",
                    ),
                ),
                ReportSection(
                    "recommended_follow_up",
                    "後續調查建議",
                    51,
                    (
                        "建議優先核對高頻交易對手、Provider 缺漏、Local Label 來源及 Evidence 完整性。",
                    ),
                ),
                ReportSection(
                    "limitations",
                    "資料限制",
                    60,
                    tuple(item.description for item in limitations),
                    limitations=limitations,
                ),
                ReportSection(
                    "conclusion",
                    "綜合研判",
                    70,
                    (
                        self._conclusion(
                            completeness, len(errors), len(rejected), investigation
                        ).text,
                    ),
                ),
                ReportSection(
                    "evidence_index",
                    "Evidence Index",
                    80,
                    (
                        "僅列 artifact-level Evidence；record-level mapping 請參閱 report_data.json。",
                        (
                            "部分舊版 fixture 未保存 SHA-256，以下以「雜湊不可用」標示，"
                            "不得視為已驗證。"
                            if any(not item.hash for item in evidence)
                            else "所有列示 artifact 均保存 SHA-256。"
                        ),
                    ),
                    tables=(self._evidence_table(evidence),),
                    evidence_refs=tuple(item.evidence_id for item in evidence),
                ),
                ReportSection(
                    "appendix",
                    "技術附錄",
                    90,
                    (
                        "完整 metadata、record-level mapping 與原始精度請參閱 report_data.json 及案件 artifacts。",
                    ),
                    tables=(self._address_appendix(counterparties, investigation),),
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
    def _conclusion(completeness, error_count, rejected_count, investigation=None):
        if investigation:
            meta = investigation.get("structured_metadata") or {}
            funding = investigation.get("funding", {})
            patterns = investigation.get("transfer_patterns", {})
            dormant = investigation.get("dormant_periods", [])
            distribution = investigation.get("distribution_analysis") or {}
            assets = ", ".join(meta.get("assets", [])) or "無"
            source_from = meta.get("source_date_from") or "未知"
            source_to = meta.get("source_date_to") or "未知"
            rapid = any(
                item.get("within_1_hour_ratio", 0)
                for item in (distribution.get("statistics_by_asset") or {}).values()
            )
            concentration = "；".join(
                f"{asset} {format_percent(value)}"
                for asset, value in sorted(
                    (funding.get("concentration_by_asset") or {}).items()
                )
            ) or "無可用資料"
            fixed_pattern = (
                "有辨識到"
                if any(patterns.get("fixed_amounts", {}).values())
                else "未辨識到"
            )
            rapid_pattern = "有辨識到" if rapid else "未辨識到"
            text = (
                f"本次分析期間為 {source_from} 至 {source_to}，共納入 "
                f"{meta.get('source_transaction_count', 0)} 筆可供 Investigation 使用的交易邊，"
                f"資料狀態為 {completeness}，涉及資產：{assets}。"
                f"目前樣本的供款集中度為 {concentration}；"
                f"來源切換 {len(funding.get('transitions', []))} 次；"
                f"休眠區間 {len(dormant)} 個；"
                f"批次流入／流出視窗為 {patterns.get('batch_incoming_count', 0)}/"
                f"{patterns.get('batch_outgoing_count', 0)}；"
                f"{fixed_pattern}固定金額模式；"
                f"{rapid_pattern}一小時內完成 FIFO 配對的事件。"
                "以上只描述目前樣本；Local Label 與 Provider 缺漏可能改變排行與模式。"
                "僅依鏈上資料無法判定實際控制人、交易目的或犯罪意圖。"
            )
            return ReportConclusion(completeness, text)
        if completeness == "failed":
            text = "資料處理未形成足夠的有效交易結果；本報告僅記錄可驗證的失敗狀態與限制。"
        elif completeness == "partial":
            text = "本報告依部分資料產生；結果可供初步調查，但必須連同缺漏、Provider 錯誤與拒絕紀錄解讀。"
        else:
            text = "本報告已依目前取得的完整資料產生；內容僅為交易資料的描述性整理，不代表犯罪、風險或身分判定。"
        return ReportConclusion(completeness, text)

    @classmethod
    def _investigation_sections(
        cls,
        investigation,
        data,
        completeness,
        graph=None,
        statuses=(),
        timezone="UTC",
    ):
        reconciliation = investigation.get("direction_reconciliation") or {}
        funding = investigation.get("funding") or {}
        distribution = investigation.get("distribution_analysis") or {}
        stages = investigation.get("stages") or []
        dormant = investigation.get("dormant_periods") or []
        patterns = investigation.get("transfer_patterns") or {}
        services = investigation.get("services") or []
        observations = investigation.get("observations") or []
        facts = investigation.get("conclusion_fact_items") or []
        source_rows = []
        for asset, addresses in sorted(
            (funding.get("top_sources_by_asset") or {}).items()
        ):
            indexed = {
                item.get("address"): item for item in funding.get("sources", [])
            }
            for rank, address in enumerate(addresses[:10], 1):
                item = indexed[address]
                source_rows.append(
                    (
                        str(rank), asset, address,
                        format_value(item.get("amounts_by_asset", {}).get(asset, 0)),
                        format_percent(
                            item.get("share_by_asset", {}).get(asset, 0)
                        ),
                        format_datetime(item.get("first_funding"), timezone),
                        format_datetime(item.get("last_funding"), timezone),
                    )
                )
        counterparty_rows = []
        service_map = {
            item.get("address"): cls._neutral_candidate_role(
                item.get("service_type"),
                bool(item.get("label")),
            )
            for item in services
        }
        counterparties = data.get("counterparties", [])
        outgoing_assets = sorted({
            asset
            for item in counterparties
            for asset in item.get("outgoing_amount_by_asset", {})
        })
        for asset in outgoing_assets:
            candidates = [
                item for item in counterparties
                if item.get("outgoing_amount_by_asset", {}).get(asset, 0)
            ]
            candidates.sort(
                key=lambda item: (
                    -Decimal(str(item["outgoing_amount_by_asset"][asset])),
                    item.get("address", ""),
                )
            )
            total = sum(
                (
                    Decimal(str(item["outgoing_amount_by_asset"][asset]))
                    for item in candidates
                ),
                Decimal("0"),
            )
            for rank, item in enumerate(candidates[:10], 1):
                incoming = item.get("incoming_amount_by_asset", {})
                outgoing = item.get("outgoing_amount_by_asset", {})
                counterparty_rows.append(
                    (
                        str(rank), item.get("address", ""),
                        "流出",
                        str(item.get("interaction_count", 0)),
                        asset,
                        format_amount(incoming.get(asset, 0)),
                        format_amount(outgoing.get(asset, 0)),
                        format_datetime(item.get("first_seen"), timezone),
                        format_datetime(item.get("last_seen"), timezone),
                        service_map.get(item.get("address"), "unknown candidate"),
                    )
                )
        stage_rows = tuple(
            (
                cls._human_stage(item.get("stage")),
                format_datetime(item.get("started_at"), timezone),
                format_datetime(item.get("ended_at"), timezone),
                str(item.get("transaction_count", 0)),
                format_compact(item.get("assets", [])),
                cls._address_list(item.get("dominant_funding_sources", [])),
                cls._address_list(item.get("dominant_outgoing_counterparties", [])),
                cls._human_reasons(item.get("reason_codes", [])),
                item.get("confidence", "low" if completeness != "complete" else "medium"),
                format_compact(item.get("limitations", [])),
            )
            for item in stages
        )
        holding_rows = tuple(
            (
                asset,
                format_value(item.get("matched_incoming_amount")),
                format_value(item.get("matched_outgoing_amount")),
                format_value(item.get("unmatched_incoming_amount")),
                format_value(item.get("unmatched_outgoing_amount")),
                format_duration(item.get("average_holding_seconds")),
                format_duration(item.get("median_holding_seconds")),
                format_percent(item.get("within_1_hour_ratio", 0)),
                format_percent(item.get("within_24_hours_ratio", 0)),
                str(item.get("pass_through_event_count", 0)),
            )
            for asset, item in sorted(
                (distribution.get("statistics_by_asset") or {}).items()
            )
        )
        observation_rows = tuple(
            (
                item.get("factual_statement", "") or cls._human_code(item.get("code")),
                cls._reference_ids(item.get("evidence_refs", [])),
                item.get("confidence", "medium"),
                format_compact(item.get("limitations", [])),
            )
            for item in observations
        )
        graph_truncated = bool(
            (graph or {}).get("metadata", {}).get("truncated", False)
        )
        provider_truncated = any(
            bool(item.get("truncated")) for item in statuses
        )
        canonical_fact_values = {
            "graph_truncated": graph_truncated,
            "provider_truncated": provider_truncated,
        }
        fact_rows = tuple(
            (
                cls._fact_statement(
                    item.get("fact_code"),
                    canonical_fact_values.get(
                        item.get("fact_code"), item.get("value")
                    ),
                    item.get("unit"),
                ),
                cls._reference_ids(item.get("evidence_refs", [])),
                item.get("confidence", "medium"),
                format_compact(item.get("limitations", [])),
            )
            for item in facts
        )
        return (
            ReportSection(
                "investigation", "調查特徵", 10,
                (
                    "本節為 deterministic rule engine 結果，不使用 AI、風險分數或身分推論。",
                    f"資料完整度：{completeness}。",
                ),
            ),
            ReportSection(
                "direction_reconciliation", "方向對帳", 11,
                ("處理失敗的交易另行排除；目前數量列於表中。",),
                tables=(ReportTable(
                    "direction_reconciliation",
                    "方向對帳",
                    ("項目", "筆數"),
                    (
                        (
                            "處理失敗",
                            str(reconciliation.get("failed_transaction_count", 0)),
                        ),
                        (
                            "方向未分類",
                            str(reconciliation.get("unclassified_direction_count", 0)),
                        ),
                    ),
                ),),
            ),
            ReportSection(
                "funding_analysis", "各資產供款來源", 12,
                tables=(
                    ReportTable(
                        "funding_sources", "各資產前十大供款來源",
                        ("排名", "資產", "地址", "金額", "占比", "首次", "最後"),
                        tuple(source_rows),
                    ),
                    cls._funding_transition_table(
                        funding.get("transitions", []), timezone
                    ),
                ),
            ),
            ReportSection(
                "outgoing_distribution", "主要資金去向與角色候選", 13,
                ("無 Local Label 時，service／exchange／payment／OTC 僅表示規則候選。",),
                tables=(ReportTable(
                    "counterparty_summary", "主要交易對手橫向摘要",
                    ("排名", "地址", "方向", "交易次數", "主要資產",
                     "流入金額", "流出金額", "首次出現", "最後出現", "標籤／候選角色"),
                    tuple(counterparty_rows),
                ),),
            ),
            ReportSection(
                "operation_stages", "運作階段", 14,
                tables=(ReportTable(
                    "operation_stages", "Operation Stages",
                    ("階段", "開始", "結束", "交易數", "資產", "主要來源",
                     "主要去向", "判定依據", "信心", "資料限制"),
                    stage_rows,
                ),),
            ),
            ReportSection(
                "dormancy", "休眠與重新啟用", 15,
                (
                    (
                        "目前已取得資料中未偵測到休眠；因資料不完整，無法排除範圍外休眠區間。"
                        if not dormant and completeness != "complete"
                        else f"目前範圍偵測區間數：{len(dormant)}。"
                    ),
                    "本報告不把資料邊界本身視為休眠證據。",
                ),
                tables=(cls._records_table("dormancy", "休眠區間", dormant),) if dormant else (),
            ),
            ReportSection(
                "holding_time", "資金停留時間", 16,
                ("採 FIFO approximation、不得解讀為實際同一筆資金流向，且不跨資產配對。",),
                tables=(ReportTable(
                    "holding_time", "依資產分離之 FIFO 統計",
                    ("資產", "配對流入", "配對流出", "未配對流入", "未配對流出",
                     "平均停留時間", "中位停留時間", "1 小時內比例", "24 小時內比例", "事件數"),
                    holding_rows,
                ),),
            ),
            ReportSection(
                "transfer_patterns", "轉帳模式", 17,
                (
                    "門檻來自 settings snapshot；dust／spam candidate 不列為重要固定金額模式。",
                    (
                        "目前資料未偵測到的模式不代表完整歷史中不存在。"
                        if completeness != "complete"
                        else "判定僅限目前完整取得的分析範圍。"
                    ),
                ),
                tables=(cls._pattern_table(patterns),),
            ),
            ReportSection(
                "investigation_observations", "客觀觀察", 18,
                tables=(ReportTable(
                    "investigation_observations", "Deterministic Observations",
                    ("規則式觀察", "引用", "信心", "資料限制"),
                    observation_rows,
                ),),
                observation_refs=tuple(
                    str(item.get("code"))
                    for item in observations
                    if item.get("code")
                ),
            ),
            ReportSection(
                "investigation_facts", "已確認資料事實", 19,
                tables=(ReportTable(
                    "investigation_facts", "結論事實",
                    ("已確認資料事實", "引用", "信心", "資料限制"),
                    fact_rows,
                ),),
                fact_refs=tuple(
                    str(item.get("fact_code"))
                    for item in facts
                    if item.get("fact_code")
                ),
            ),
        )

    @staticmethod
    def _neutral_candidate_role(value, label_confirmed=False):
        role = str(value or "unknown_candidate")
        if label_confirmed and role in {"payment", "exchange", "otc", "service"}:
            return {
                "payment": "已標記支付服務",
                "exchange": "已標記交易所",
                "otc": "已標記 OTC",
                "service": "已標記服務商",
            }[role]
        return {
            "possible_payment": "高頻流出交易對手候選",
            "possible_service": "服務型交易對手候選",
            "payment": "重複收款地址候選",
            "otc": "中介型交易對手候選",
            "service": "服務型交易對手候選",
            "exchange": "交易所候選",
            "unknown": "未分類候選",
            "unknown_candidate": "未分類候選",
        }.get(role, "未分類候選")

    @staticmethod
    def _address_list(values):
        visible = tuple(str(item) for item in values[:3])
        suffix = f"；省略 {len(values) - 3} 筆，完整清單見附錄" if len(values) > 3 else ""
        return "、".join(visible) + suffix if visible else "—"

    @staticmethod
    def _human_stage(value):
        return {
            "activation": "啟動期",
            "startup": "啟動期",
            "dominant": "主導期",
            "diversification": "來源多元化",
            "dormant": "停用期",
            "recovery": "恢復期",
        }.get(str(value), str(value or "—"))

    @staticmethod
    def _human_reasons(values):
        labels = {
            "monthly_dominant_source_changed": "每月主要供款來源改變",
            "frequency_increased": "交易頻率增加",
            "frequency_decreased": "交易頻率下降",
            "concentration_changed": "供款集中度改變",
            "first_sample_window": "首個活動樣本區間",
            "funding_concentration_threshold": "供款集中度達規則門檻",
        }
        return "、".join(labels.get(str(item), str(item)) for item in values) or "—"

    @staticmethod
    def _reference_ids(values):
        return "、".join(str(item) for item in values[:5]) or "—"

    @staticmethod
    def _human_code(code):
        return {
            "dominant_funder_exists": "目前分析範圍內存在主要供款來源。",
            "funding_source_changed": "目前分析範圍內主要供款來源曾發生切換。",
            "dormant_period_detected": "目前分析範圍內辨識到休眠期間。",
            "fixed_amount_pattern_detected": "目前資料中符合固定金額模式。",
            "provider_truncated": "Provider 資料取得曾發生截斷。",
            "graph_truncated": "交易關係圖因安全上限發生截斷。",
            "analysis_partial": "分析資料為部分範圍。",
            "batch_incoming_detected": "目前資料中符合批次流入模式。",
            "batch_outgoing_detected": "目前資料中符合批次流出模式。",
            "rapid_pass_through_detected": "目前資料中符合快速轉出模式。",
            "reactivation_detected": "目前資料中辨識到重新啟用。",
        }.get(str(code), str(code or "—").replace("_", " "))

    @classmethod
    def _fact_statement(cls, code, value, unit=None):
        if isinstance(value, (Mapping, tuple, list, set, frozenset)):
            labels = {
                "dominant_funder_address": "各資產主要供款來源地址",
                "dominant_funder_share_by_asset": "各資產主要供款來源占比",
            }
            return (
                f"{labels.get(str(code), cls._human_code(code).rstrip('。'))}"
                "已保存；完整對照見 report_data.json。"
            )
        if isinstance(value, bool):
            state = "有" if value else "未"
            return f"{state}辨識到「{cls._human_code(code).rstrip('。')}」。"
        rendered = format_compact(value)
        unit_text = {
            None: "",
            "": "",
            "—": "",
            "count": " 筆",
            "days": " 天",
        }.get(unit, f" {format_compact(unit)}")
        labels = {
            "transaction_count": "分析期間納入交易筆數",
            "funding_transition_count": "主要供款來源切換次數",
            "dormant_days": "休眠天數",
            "batch_outgoing_count": "批次流出視窗數",
            "batch_incoming_count": "批次流入視窗數",
            "longest_dormant_days": "最長休眠天數",
            "service_candidate_count": "服務型態候選數",
            "unknown_direction_count": "方向未分類筆數",
        }
        return f"{labels.get(str(code), str(code).replace('_', ' '))}：{rendered}{unit_text}。"

    @classmethod
    def _funding_transition_table(cls, records, timezone):
        return ReportTable(
            "funding_transitions",
            "供款來源變化",
            ("資產", "前一主要來源", "新主要來源", "發生時間",
             "前一占比", "新占比", "原因", "信心", "限制"),
            tuple(
                (
                    format_value(item.get("asset")),
                    format_value(item.get("previous_source")),
                    format_value(item.get("current_source")),
                    format_datetime(item.get("occurred_at"), timezone),
                    format_percent(item.get("old_source_share", 0)),
                    format_percent(item.get("new_source_share", 0)),
                    cls._human_reasons(item.get("reason_codes", [])),
                    format_value(item.get("confidence", "medium")),
                    format_compact(item.get("limitations", [])),
                )
                for item in records
            ),
        )

    @staticmethod
    def _pattern_table(patterns):
        fixed = []
        for asset, amounts in sorted((patterns.get("fixed_amounts") or {}).items()):
            values = "、".join(format_amount(item) for item in amounts[:8])
            if values:
                fixed.append(f"{asset}：{values}")
        return ReportTable(
            "transfer_patterns",
            "模式摘要",
            ("判讀項目", "結果"),
            (
                ("整數金額比例", format_percent(patterns.get("integer_amount_ratio", 0))),
                ("批次流入視窗數", str(patterns.get("batch_incoming_count", 0))),
                ("批次流出視窗數", str(patterns.get("batch_outgoing_count", 0))),
                ("主要固定金額", "；".join(fixed) or "未辨識"),
                ("資料限制", "僅反映目前分析範圍；完整精度見 report_data.json。"),
            ),
        )

    @staticmethod
    def _evidence_table(evidence):
        selected = {}
        for item in evidence:
            key = item.source
            current = selected.get(key)
            if current is None or (
                str(current.evidence_id).startswith("IF")
                and not str(item.evidence_id).startswith("IF")
            ):
                selected[key] = item
        rows = []
        for source, item in sorted(selected.items()):
            available = bool(item.hash)
            evidence_id = str(item.evidence_id)
            if evidence_id.startswith("IF"):
                evidence_id = "LEGACY-ARTIFACT"
            rows.append(
                (
                    evidence_id,
                    Path(source).name,
                    str(item.evidence_type),
                    (
                        f"{str(item.hash)[:12]}…"
                        if available
                        else "雜湊不可用"
                    ),
                    "已驗證" if available else "無法驗證",
                    str(item.source_reference or item.source),
                    item.description or ("舊版 fixture 未保存 SHA-256" if not available else "—"),
                )
            )
        return ReportTable(
            "artifact_evidence_index",
            "Artifact Evidence Index",
            ("Evidence ID", "檔名", "類型", "SHA-256", "完整性", "來源", "備註"),
            tuple(rows),
        )

    @staticmethod
    def _address_appendix(counterparties, investigation):
        rows = []
        seen = set()
        for item in counterparties:
            address = str(item.get("address") or "")
            if address and address not in seen:
                seen.add(address)
                rows.append(("交易對手", address))
        funding = (investigation or {}).get("funding") or {}
        top_addresses = {
            str(address)
            for addresses in (funding.get("top_sources_by_asset") or {}).values()
            for address in addresses[:10]
        }
        for item in funding.get("sources", []):
            address = str(item.get("address") or "")
            if address and address in top_addresses and address not in seen:
                seen.add(address)
                rows.append(("供款來源", address))
        return ReportTable(
            "full_address_appendix",
            "完整地址對照",
            ("類型", "完整地址"),
            tuple(rows),
        )

    @staticmethod
    def _pipeline_counts(data, graph, investigation, time_scope):
        metadata = data.get("metadata", {})
        summary = data.get("summary", {})
        reconciliation = (investigation or {}).get("direction_reconciliation", {})
        graph_metadata = (graph or {}).get("metadata", {})
        scope_type = (
            (metadata.get("analysis_scope") or {}).get("scope_type")
            or time_scope.get("scope_type")
            or "unavailable"
        )
        rows = (
            (
                "Provider 原始取得",
                str(metadata.get("provider_raw_record_count", summary.get("transaction_count", 0))),
                format_value(time_scope.get("overall_first_seen")),
                format_value(time_scope.get("overall_last_seen")),
                scope_type,
                "—",
            ),
            (
                "正規化後",
                str(metadata.get("normalized_record_count", summary.get("transaction_count", 0))),
                format_value(summary.get("first_seen")),
                format_value(summary.get("last_seen")),
                scope_type,
                f"拒絕 {metadata.get('rejected_record_count', 0)} 筆；去重 {metadata.get('deduplicated_record_count', 0)} 筆",
            ),
            (
                "Analysis 使用",
                str(metadata.get("analysis_record_count", summary.get("transaction_count", 0))),
                format_value(summary.get("first_seen")),
                format_value(summary.get("last_seen")),
                scope_type,
                f"分析範圍外排除 {metadata.get('excluded_by_scope', time_scope.get('excluded_by_scope', 0))} 筆",
            ),
            (
                "Investigation 使用交易邊",
                str(
                    (investigation or {})
                    .get("structured_metadata", {})
                    .get("source_transaction_count", 0)
                ),
                format_value(
                    (investigation or {})
                    .get("structured_metadata", {})
                    .get("source_date_from")
                ),
                format_value(
                    (investigation or {})
                    .get("structured_metadata", {})
                    .get("source_date_to")
                ),
                scope_type,
                f"處理失敗 {reconciliation.get('failed_transaction_count', 0)} 筆；方向未分類 {reconciliation.get('unclassified_direction_count', 0)} 筆",
            ),
            (
                "Graph 使用",
                str(graph_metadata.get("included_edge_count", len((graph or {}).get("edges", [])))),
                "—",
                "—",
                scope_type,
                (
                    f"節點 {graph_metadata.get('included_node_count', len((graph or {}).get('nodes', [])))} 個；"
                    + ("已截斷" if graph_metadata.get("truncated", False) else "未截斷")
                ),
            ),
        )
        return ReportTable(
            "data_pipeline_counts",
            "各階段資料母體",
            ("階段", "紀錄／邊", "最早", "最晚", "範圍", "排除／限制"),
            rows,
        )

    @staticmethod
    def _provider_table(records):
        columns = (
            "鏈別",
            "Capability",
            "Provider",
            "取得筆數",
            "完整度",
            "截斷",
            "截斷原因",
            "警告",
        )
        rows = tuple(
            (
                format_value(item.get("chain")),
                format_value(item.get("capability")),
                format_value(item.get("provider")),
                format_value(item.get("fetched_records")),
                format_value(item.get("completeness")),
                "是" if item.get("truncated", False) else "否",
                format_value(item.get("truncation_reason")),
                format_value(item.get("warnings", ())),
            )
            for item in records
        )
        return ReportTable("providers", "Provider 狀態", columns, rows)

    @staticmethod
    def _asset_presentation_table(records, *, appendix=False):
        if appendix:
            reason_labels = {
                "advertisement_name_single_inbound_candidate": (
                    "僅單次流入、未觀察到流出，且資產名稱帶有網址、社群帳號"
                    "或廣告形式；列為低重要性 spam candidate 供人工覆核。"
                ),
                "spam_candidate": (
                    "低於 materiality threshold、僅少量流入且未觀察到流出；"
                    "列為 spam／dust candidate 供人工覆核。"
                ),
                "below_materiality_threshold": (
                    "低於 materiality threshold；移至附錄並保留原始 Evidence。"
                ),
                "user_excluded": "由使用者明確排除；可隨時恢復。",
            }
            return ReportTable(
                "non_material_asset_candidates",
                "低重要性及 Spam Candidate 項目",
                (
                    "資產", "流入金額", "流出金額", "交易次數",
                    "排除類別", "排除原因", "Evidence", "信心",
                    "人工審閱", "可恢復",
                ),
                tuple(
                    (
                        item.asset,
                        format_amount(item.incoming),
                        format_amount(item.outgoing),
                        str(item.transaction_count),
                        "spam／低重要性候選",
                        reason_labels.get(item.reason, item.reason),
                        "analysis.json",
                        "medium",
                        "尚未審閱",
                        "是",
                    )
                    for item in records
                ),
            )
        return ReportTable(
            "asset_flows",
            "依資產分離之流入／流出",
            ("資產", "流入", "流出", "交易數", "分類", "原因"),
            tuple(
                (
                    item.asset,
                    format_amount(item.incoming),
                    format_amount(item.outgoing),
                    str(item.transaction_count),
                    (
                        "spam candidate"
                        if item.spam_candidate
                        else "dust"
                        if item.dust
                        else "material"
                    ),
                    item.reason,
                )
                for item in records
            ),
        )

    @staticmethod
    def _mapping_table(table_id, title, values):
        return ReportTable(
            table_id,
            title,
            ("指標", "值"),
            tuple(
                (str(key), format_compact(value))
                for key, value in values.items()
            ),
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
        columns = (
            "排名", "地址", "方向", "交易次數", "主要資產",
            "流入金額", "流出金額", "首次出現", "最後出現", "標籤／候選角色",
        )
        rows = []
        for rank, item in enumerate(records, 1):
            incoming = item.get("incoming_amount_by_asset") or {}
            outgoing = item.get("outgoing_amount_by_asset") or {}
            assets = sorted(
                set(incoming) | set(outgoing),
                key=lambda asset: -(
                    Decimal(str(incoming.get(asset, 0)))
                    + Decimal(str(outgoing.get(asset, 0)))
                ),
            )
            primary = assets[0] if assets else "—"
            rows.append(
                (
                    str(rank),
                    format_value(item.get("address")),
                    {"incoming": "流入", "outgoing": "流出", "mixed": "雙向"}.get(
                        str(item.get("direction")), format_value(item.get("direction"))
                    ),
                    str(item.get("interaction_count", 0)),
                    primary,
                    format_amount(incoming.get(primary, 0)) if primary != "—" else "0",
                    format_amount(outgoing.get(primary, 0)) if primary != "—" else "0",
                    format_value(item.get("first_seen")),
                    format_value(item.get("last_seen")),
                    format_value(
                        item.get("label")
                        or item.get("candidate_role")
                        or "未標記"
                    ),
                )
            )
        return ReportTable(
            "counterparties",
            "主要交易對手",
            columns,
            tuple(rows),
        )

    @staticmethod
    def _asset_time_table(records, time_scope, timezone):
        first = time_scope.get("first_seen_by_asset") or {}
        last = time_scope.get("last_seen_by_asset") or {}
        assets = {item.asset for item in records}
        return ReportTable(
            "asset_time_scope",
            "重要資產時間範圍",
            ("資產", "首次交易時間", "最後交易時間"),
            tuple(
                (
                    asset,
                    format_datetime(first.get(asset), timezone),
                    format_datetime(last.get(asset), timezone),
                )
                for asset in sorted(assets)
                if first.get(asset) or last.get(asset)
            ),
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
            tuple(
                tuple(format_compact(item.get(key)) for key in keys)
                for item in records
            ),
        )
