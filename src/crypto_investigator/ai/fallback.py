from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json

from crypto_investigator.narratives.models import (
    NarrativeCitation,
    NarrativeClaim,
    NarrativeInput,
    NarrativeMetadata,
    NarrativeParagraph,
    NarrativeResult,
    NarrativeSection,
    NarrativeValidationResult,
    NarrativeWarning,
)
from crypto_investigator.narratives.sections import SECTION_TITLES


class DeterministicFallbackProvider:
    provider_name = "deterministic-fallback"
    model_name = "template-v1"
    supports_json_schema = True
    supports_streaming = False

    def generate(self, source: NarrativeInput) -> NarrativeResult:
        digest = sha256(
            json.dumps(asdict(source), sort_keys=True, default=str).encode()
        ).hexdigest()
        generated_at = self._stable_generated_at(source)
        evidence_ids = tuple(str(item["evidence_id"]) for item in source.evidence_index if item.get("evidence_id"))
        evidence_id = evidence_ids[0] if evidence_ids else None
        citation = (
            NarrativeCitation("C1", evidence_id, "executive_summary"),
        ) if evidence_id else ()
        period = f"{source.analysis_period.get('from') or '未知'} 至 {source.analysis_period.get('to') or '未知'}"
        count = source.report_metadata.get("transaction_count", 0)
        summary = (
            f"分析期間為 {period}，結構化樣本共 {count} 筆，完整度為 {source.completeness}。"
            "本段僅整理 V6.5 已驗證事實，不作犯罪、身分或風險判定。"
        )
        sections = {
            "executive_summary": self._section("executive_summary", summary, evidence_id),
            "target_profile": self._section("target_profile", f"分析標的：{source.target_address}；鏈別：{source.chain or '未知'}。", evidence_id),
            "funding_narrative": self._funding(source, evidence_id),
            "outgoing_narrative": self._section("outgoing_narrative", "僅依目前結構化去向排行描述；若無資料，無法判定主要流出去向。", evidence_id),
            "stage_narrative": self._section("stage_narrative", f"既有 Investigation Engine 共辨識 {len(source.operation_stages)} 個運作階段；未新增任何階段。", evidence_id),
            "dormancy_narrative": self._section("dormancy_narrative", f"既有結果記錄 {len(source.dormancy)} 個休眠期間；Provider 缺漏不視為休眠。", evidence_id),
            "holding_time_narrative": self._section("holding_time_narrative", "資金停留時間依 FIFO 近似配對，不代表實際同一筆資金的追蹤。", evidence_id),
            "pattern_narrative": self._section("pattern_narrative", f"結構化結果包含 {len(source.transfer_patterns)} 個模式項目，單次事件不據此擴大解讀。", evidence_id),
            "counterparty_narrative": self._section("counterparty_narrative", "交易對手角色均為規則式候選，不代表身分確認。", evidence_id),
            "alternative_explanations": self._section("alternative_explanations", "可能為營運型結算、代付、資金調度或未知服務型用途；目前資料尚不能排除其他解釋。", evidence_id),
            "investigative_leads": self._section("investigative_leads", "可依現有證據補充本地標籤、提高資料取得上限，並查核主要供款與出金對象；本系統不自動執行。", evidence_id),
            "limitations": self._section("limitations", "；".join(source.limitations) if source.limitations else "未提供額外限制；仍僅能就目前樣本陳述。", None),
            "conclusion": self._section("conclusion", summary + " 所有候選角色與替代解釋均保留不確定語意。", evidence_id),
        }
        claim = NarrativeClaim(
            "CL1", "executive_summary", summary, "factual",
            evidence_ids=(evidence_id,) if evidence_id else (),
            numeric_values=(str(count),),
            limitations=source.limitations,
        )
        return NarrativeResult(
            metadata=NarrativeMetadata(
                self.provider_name, self.model_name, "7.0.0",
                generated_at, "fallback", True, digest,
            ),
            **{key: value for key, value in sections.items() if key in source.requested_sections},
            claims=(claim,), citations=citation,
            warnings=(NarrativeWarning("AI_FALLBACK", "使用 deterministic fallback 敘事"),),
            validation=NarrativeValidationResult(valid=True, checked_claims=1),
        )

    @staticmethod
    def _section(section_id, text, evidence_id):
        citations = ("C1",) if evidence_id else ()
        return NarrativeSection(section_id, SECTION_TITLES[section_id], (NarrativeParagraph(text, citations),))

    def _funding(self, source, evidence_id):
        if not source.funding_sources:
            text = "目前結構化資料不足以描述主要供款來源。"
        else:
            top = source.funding_sources[0]
            text = f"目前樣本的主要供款來源候選為 {top.get('address', '未知')}，排名 {top.get('rank', 1)}；不代表主控方。"
        return self._section("funding_narrative", text, evidence_id)

    def health_check(self):
        return True

    @property
    def usage_metadata(self):
        return {}

    @staticmethod
    def _stable_generated_at(source):
        raw = source.analysis_period.get("to") or source.analysis_period.get("from")
        if raw:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
