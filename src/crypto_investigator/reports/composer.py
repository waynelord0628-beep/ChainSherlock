from pathlib import Path
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4
from dataclasses import replace

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
            evidence = evidence + tuple(
                ReportEvidence(
                    evidence_id=str(item.get("evidence_id")),
                    evidence_type=str(item.get("feature", "investigation")),
                    source="investigation_evidence.json",
                    source_reference=str(
                        item.get("source_reference", "AnalysisResult.flow")
                    ),
                    description=str(item.get("calculation", "")),
                    collected_at=item.get("created_at"),
                    tx_hash=(
                        item.get("tx_hashes", [None])[0]
                        if item.get("tx_hashes") else None
                    ),
                    address=(
                        item.get("addresses", [None])[0]
                        if item.get("addresses") else None
                    ),
                    metadata={
                        "transaction_hashes": item.get("tx_hashes", []),
                        "addresses": item.get("addresses", []),
                        "parameters": item.get("parameters", {}),
                    },
                )
                for item in investigation_data.get("evidence_refs", [])
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
            target_address,
            chain,
            investigation_data,
        )
        if narrative is not None:
            sections = tuple(sorted(
                (*sections, *self._narrative_sections(narrative)),
                key=lambda item: (item.order, item.section_id),
            ))
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

    @staticmethod
    def _narrative_sections(narrative):
        if not getattr(narrative, "validation", None) or not narrative.validation.valid:
            return ()
        metadata = narrative.metadata
        review = getattr(narrative.review_status, "value", narrative.review_status)
        header = (
            "AI 輔助敘事；"
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
                    f"ai_{name}", f"AI 輔助敘事：{redact(section.title)}", order,
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
                    f"標的：{redact(target_address or '—')}",
                    f"鏈別：{redact(chain or '—')}",
                ),
            ),
            ReportSection(
                "completeness",
                "資料完整度",
                3,
                (
                    f"分析完整度：{completeness}。",
                    f"Provider 錯誤：{len(errors)} 筆。",
                    f"被拒絕資料：{len(rejected)} 筆。",
                ),
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
        if investigation:
            sections.extend(
                self._investigation_sections(
                    investigation, data, completeness
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
                ReportSection(
                    "conclusion",
                    "結論",
                    30,
                    (
                        self._conclusion(
                            completeness, len(errors), len(rejected), investigation
                        ).text,
                    ),
                ),
                ReportSection(
                    "evidence_index",
                    "Evidence Index",
                    31,
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
                    32,
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
            text = (
                f"本次分析期間為 {source_from} 至 {source_to}，共納入 "
                f"{meta.get('source_transaction_count', 0)} 筆可供 Investigation 使用的交易邊，"
                f"資料狀態為 {completeness}，涉及資產：{assets}。"
                f"目前樣本的 funding concentration 為 "
                f"{format_value(funding.get('concentration_by_asset', {}))}；"
                f"來源切換 {len(funding.get('transitions', []))} 次；"
                f"休眠區間 {len(dormant)} 個；"
                f"batch incoming/outgoing 為 {patterns.get('batch_incoming_count', 0)}/"
                f"{patterns.get('batch_outgoing_count', 0)}；"
                f"固定金額模式為 {bool(any(patterns.get('fixed_amounts', {}).values()))}；"
                f"一小時內 FIFO 配對比例非零為 {rapid}。"
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
    def _investigation_sections(cls, investigation, data, completeness):
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
                        format_value(item.get("share_by_asset", {}).get(asset, 0)),
                        format_value(item.get("first_funding")),
                        format_value(item.get("last_funding")),
                    )
                )
        counterparty_rows = []
        service_map = {item.get("address"): item.get("service_type") for item in services}
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
                        str(rank), item.get("address", ""), "",
                        service_map.get(item.get("address"), "unknown candidate"),
                        "outgoing", str(item.get("interaction_count", 0)), asset,
                        format_value(incoming.get(asset, 0)),
                        format_value(outgoing.get(asset, 0)),
                        format_value(
                            Decimal(str(outgoing.get(asset, 0))) / total
                            if total else 0
                        ),
                        format_value(item.get("first_seen")),
                        format_value(item.get("last_seen")),
                    )
                )
        stage_rows = tuple(
            (
                item.get("stage", ""), format_value(item.get("started_at")),
                format_value(item.get("ended_at")),
                str(item.get("transaction_count", 0)),
                format_value(item.get("assets", [])),
                format_value(item.get("dominant_funding_sources", [])),
                format_value(item.get("dominant_outgoing_counterparties", [])),
                format_value(item.get("reason_codes", [])),
                item.get("confidence", "low" if completeness != "complete" else "medium"),
                format_value(item.get("evidence_refs", [])),
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
                format_value(item.get("average_holding_seconds")),
                format_value(item.get("median_holding_seconds")),
                format_value(item.get("within_5_minutes_ratio")),
                format_value(item.get("within_1_hour_ratio")),
                format_value(item.get("within_24_hours_ratio")),
                str(item.get("pass_through_event_count", 0)),
            )
            for asset, item in sorted(
                (distribution.get("statistics_by_asset") or {}).items()
            )
        )
        observation_rows = tuple(
            (
                item.get("code", ""), item.get("factual_statement", ""),
                format_value(item.get("metrics", {})),
                format_value(item.get("reason_codes", [])),
                format_value(item.get("evidence_refs", [])),
                item.get("confidence", "medium"),
                format_value(item.get("limitations", [])),
            )
            for item in observations
        )
        fact_rows = tuple(
            (
                item.get("fact_code", ""), format_value(item.get("value")),
                format_value(item.get("unit")), item.get("confidence", "medium"),
                format_value(item.get("reason_codes", [])),
                format_value(item.get("evidence_refs", [])),
                format_value(item.get("limitations", [])),
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
                ("failed transaction 另行排除；目前數量列於表中。",),
                tables=(cls._mapping_table("direction_reconciliation", "方向對帳", reconciliation),),
            ),
            ReportSection(
                "funding_analysis", "各資產供款來源", 12,
                tables=(
                    ReportTable(
                        "funding_sources", "各資產前十大供款來源",
                        ("排名", "資產", "地址", "金額", "占比", "首次", "最後"),
                        tuple(source_rows),
                    ),
                    cls._records_table(
                        "funding_transitions", "供款來源變化",
                        funding.get("transitions", []),
                    ),
                ),
            ),
            ReportSection(
                "outgoing_distribution", "主要資金去向與角色候選", 13,
                ("無 Local Label 時，service／exchange／payment／OTC 僅表示規則候選。",),
                tables=(ReportTable(
                    "counterparty_summary", "主要交易對手橫向摘要",
                    ("排名", "地址", "標籤", "候選角色", "方向", "交易次數",
                     "資產", "流入金額", "流出金額", "占比", "首次", "最後"),
                    tuple(counterparty_rows),
                ),),
            ),
            ReportSection(
                "operation_stages", "運作階段", 14,
                tables=(ReportTable(
                    "operation_stages", "Operation Stages",
                    ("階段", "開始", "結束", "交易數", "資產", "主要來源",
                     "主要去向", "原因", "可信度", "Evidence"),
                    stage_rows,
                ),),
            ),
            ReportSection(
                "dormancy", "休眠與重新啟用", 15,
                (
                    "partial 資料可能影響交易間隔；本報告不把資料邊界本身視為休眠證據。",
                    f"目前偵測區間數：{len(dormant)}。",
                ),
                tables=(cls._records_table("dormancy", "休眠區間", dormant),) if dormant else (),
            ),
            ReportSection(
                "holding_time", "資金停留時間", 16,
                ("採 FIFO approximation、不得解讀為實際同一筆資金流向，且不跨資產配對。",),
                tables=(ReportTable(
                    "holding_time", "依資產分離之 FIFO 統計",
                    ("資產", "配對流入", "配對流出", "未配對流入", "未配對流出",
                     "平均秒數", "中位秒數", "5 分鐘內", "1 小時內", "24 小時內", "事件數"),
                    holding_rows,
                ),),
            ),
            ReportSection(
                "transfer_patterns", "轉帳模式", 17,
                ("門檻來自 settings snapshot；dust TRX 不列為重要固定金額模式。",),
                tables=(cls._mapping_table("transfer_patterns", "模式摘要", patterns),),
            ),
            ReportSection(
                "investigation_observations", "客觀觀察", 18,
                tables=(ReportTable(
                    "investigation_observations", "Deterministic Observations",
                    ("代碼", "事實敘述", "數值", "原因", "Evidence", "可信度", "限制"),
                    observation_rows,
                ),),
            ),
            ReportSection(
                "investigation_facts", "Conclusion Facts", 19,
                tables=(ReportTable(
                    "investigation_facts", "結論事實",
                    ("Fact", "值", "單位", "可信度", "原因", "Evidence", "限制"),
                    fact_rows,
                ),),
            ),
        )

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
