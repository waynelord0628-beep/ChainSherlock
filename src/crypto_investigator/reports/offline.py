from pathlib import Path
from uuid import uuid4

from crypto_investigator.reports.citations import build_citations
from crypto_investigator.reports.ai_enrichment import AIReportIntegrator
from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.formatting import redact
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportLimitation,
    ReportMetadata,
    ReportSection,
    ReportWarning,
)
from crypto_investigator.detection.identifier import detect_identifier


class OfflineReportComposer:
    """Reconstruct a report solely from public V7 artifacts."""

    def compose(
        self,
        narrative,
        narrative_input=None,
        *,
        base_report=None,
        output_directory=".",
    ):
        if base_report is not None:
            return AIReportIntegrator().integrate(base_report, narrative)
        source = narrative_input
        chain = self._recover_chain(source)
        evidence = self._evidence(source, chain)
        limitations = tuple(
            ReportLimitation(
                f"offline_{index}",
                redact(
                    "來源分析資料不完整，可信度因此降低。"
                    if text == "Source analysis is partial; confidence is reduced."
                    else text
                ),
            )
            for index, text in enumerate(getattr(source, "limitations", ()), 1)
        )
        unavailable = []
        if source is None:
            unavailable.extend(("target_address", "chain", "analysis_period", "transaction_count"))
        if not evidence:
            unavailable.append("evidence_index")
        if unavailable:
            limitations += (
                ReportLimitation(
                    "offline_unavailable",
                    "離線 artifact 未保存以下資料，已標記 unavailable 並省略相關章節："
                    + ", ".join(unavailable),
                ),
            )
        sections = list(ReportComposer._narrative_sections(narrative))
        summary_blocks = []
        if source is not None:
            summary_blocks = [
                f"分析標的：{redact(source.target_address or 'unavailable')}",
                f"鏈別：{redact(source.chain or 'unavailable')}",
                f"分析期間：{redact(source.analysis_period.get('from') or 'unavailable')} 至 "
                f"{redact(source.analysis_period.get('to') or 'unavailable')}",
                f"資料完整度：{redact(source.completeness or 'unavailable')}",
            ]
        else:
            summary_blocks = ["公開摘要：unavailable；僅重建既存 NarrativeResult。"]
        sections.insert(0, ReportSection(
            "offline_reconstruction", "離線重建摘要", 1, tuple(summary_blocks),
            evidence_refs=tuple(item.evidence_id for item in evidence),
        ))
        sections.append(ReportSection(
            "limitations", "資料限制", 29,
            tuple(item.description for item in limitations),
            limitations=limitations,
        ))
        completeness = source.completeness if source is not None else "unavailable"
        metadata = ReportMetadata(
            report_id=f"CSR-OFFLINE-{uuid4().hex[:10].upper()}",
            report_version="7.1",
            chain=chain,
            target_address=source.target_address if source is not None else None,
            source_type="offline_artifact",
            providers=(narrative.metadata.provider,),
            analysis_completeness=completeness,
            graph_completeness="unavailable",
            transaction_count=int(source.report_metadata.get("transaction_count", 0)) if source else 0,
            language=source.language if source else "zh-TW",
            output_directory=Path(output_directory).name or ".",
        )
        warnings = (
            ReportWarning("offline_reconstruction", "本報告未重新呼叫 Provider、未讀取原始交易或 AnalysisResult。"),
        )
        return ReportDocument(
            title="ChainSherlock 離線調查敘事報告",
            metadata=metadata,
            sections=tuple(sorted(sections, key=lambda item: (item.order, item.section_id))),
            evidence=evidence,
            citations=build_citations(evidence, "offline_reconstruction"),
            warnings=warnings,
            limitations=limitations,
            conclusion=ReportConclusion(
                completeness,
                "本結論僅重建既存且已驗證的敘事；unavailable 欄位未被推測或補造。",
            ),
        )

    @staticmethod
    def _evidence(source, chain):
        if source is None:
            return ()
        return tuple(
            ReportEvidence(
                evidence_id=str(item.get("evidence_id")),
                evidence_type=str(item.get("feature", "narrative")),
                source="narrative_input.json",
                source_reference="evidence_index",
                description="離線重建使用的結構化 Evidence ID",
                chain=chain,
                address=(item.get("addresses") or (None,))[0],
                hash="未提供",
            )
            for item in source.evidence_index
            if item.get("evidence_id")
        )

    @staticmethod
    def _recover_chain(source):
        if source is None:
            return None
        if source.chain:
            return source.chain
        try:
            return detect_identifier(source.target_address).chain.value
        except Exception:
            return None
