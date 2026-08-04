from dataclasses import replace
from dataclasses import asdict, is_dataclass
import json
import re

from crypto_investigator.reports.formatting import redact
from crypto_investigator.reports.models import (
    ReportDocument,
    ReportLimitation,
    ReportSection,
    ReportWarning,
)


REQUIRED_DETERMINISTIC_SECTIONS = frozenset(
    {
        "cover",
        "target",
        "completeness",
        "analysis_summary",
        "asset_flows",
        "provider_status",
        "investigation",
        "investigation_observations",
        "investigation_facts",
        "limitations",
        "evidence_index",
    }
)

AI_SECTION_NAMES = (
    "executive_summary",
    "funding_narrative",
    "outgoing_narrative",
    "stage_narrative",
    "dormancy_narrative",
    "holding_time_narrative",
    "pattern_narrative",
    "counterparty_narrative",
    "alternative_explanations",
    "investigative_leads",
    "limitations",
    "conclusion",
)

IDENTIFIER_PATTERN = (
    r"(?:\b0x[a-fA-F0-9]{40,64}\b|"
    r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b|"
    r"(?<![A-Za-z0-9.])(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{20,70}\b)"
)


def _formalize_ai_text(value) -> str:
    text = redact(value)
    text = re.sub(r"\b(\d+)\s+days?\b", r"\1 天", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s+hours?\b", r"\1 小時", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s+minutes?\b", r"\1 分鐘", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\(UTC\+8\)", "（UTC+8）", text)
    return re.sub(
        r"\s+(?:(?:IF|E)\d+)(?:[\s,、]+(?:IF|E)\d+)*\s*$",
        "",
        text,
    )


class AIReportIntegrator:
    """Add validated narrative sections without replacing the base report."""

    minimum_section_count = 8

    def integrate(
        self,
        base: ReportDocument,
        narrative,
        *,
        fallback_baseline=None,
        validation_source=None,
    ) -> ReportDocument:
        failure = self._failure_reason(
            base, narrative, fallback_baseline, validation_source
        )
        if failure:
            return self.fallback(base, narrative, failure)

        ai_sections = self._sections(narrative)
        deterministic_sections = tuple(
            item for item in base.sections if not item.section_id.startswith("ai_")
        )
        metadata = replace(
            base.metadata,
            report_type="ai_assisted",
            base_report_version=base.metadata.report_version,
            ai_enrichment_enabled=True,
            ai_provider=redact(narrative.metadata.provider),
            ai_model=redact(narrative.metadata.model),
            prompt_version=redact(narrative.metadata.prompt_version),
            validation_status="passed",
            fallback=False,
            fallback_reason=None,
            review_status=getattr(
                narrative.review_status, "value", str(narrative.review_status)
            ),
            deterministic_section_count=len(deterministic_sections),
            ai_section_count=len(ai_sections),
            evidence_reference_count=len(
                {
                    ref
                    for section in ai_sections
                    for ref in section.evidence_refs
                }
            ),
            ai_input_tokens=getattr(narrative.metadata, "input_tokens", 0),
            ai_output_token_limit=getattr(
                narrative.metadata, "output_token_limit", 0
            ),
            ai_output_tokens=getattr(narrative.metadata, "output_tokens", 0),
            ai_finish_reason=getattr(narrative.metadata, "finish_reason", None),
        )
        return replace(
            base,
            metadata=metadata,
            sections=tuple(
                sorted(
                    (*deterministic_sections, *ai_sections),
                    key=lambda item: (item.order, item.section_id),
                )
            ),
        )

    def fallback(self, base: ReportDocument, narrative, reason: str) -> ReportDocument:
        provider = getattr(getattr(narrative, "metadata", None), "provider", None)
        model = getattr(getattr(narrative, "metadata", None), "model", None)
        metadata = replace(
            base.metadata,
            report_type="fallback",
            base_report_version=base.metadata.report_version,
            ai_enrichment_enabled=True,
            ai_provider=redact(provider) if provider else None,
            ai_model=redact(model) if model else None,
            validation_status="failed",
            fallback=True,
            fallback_reason=redact(reason),
            deterministic_section_count=len(base.sections),
            ai_section_count=0,
            evidence_reference_count=0,
            ai_input_tokens=getattr(
                getattr(narrative, "metadata", None), "input_tokens", 0
            ),
            ai_output_token_limit=getattr(
                getattr(narrative, "metadata", None), "output_token_limit", 0
            ),
            ai_output_tokens=getattr(
                getattr(narrative, "metadata", None), "output_tokens", 0
            ),
            ai_finish_reason=getattr(
                getattr(narrative, "metadata", None), "finish_reason", None
            ),
        )
        warning = ReportWarning(
            "ai_enrichment_fallback",
            f"AI enrichment 未採用；已保留完整 deterministic report。原因：{redact(reason)}",
        )
        return replace(
            base,
            metadata=metadata,
            warnings=tuple((*base.warnings, warning)),
        )

    def _failure_reason(
        self, base, narrative, fallback_baseline, validation_source=None
    ):
        section_ids = {item.section_id for item in base.sections}
        missing = sorted(REQUIRED_DETERMINISTIC_SECTIONS - section_ids)
        if missing:
            return "missing deterministic sections: " + ", ".join(missing)
        if not base.metadata.target_address:
            return "target address unavailable"
        if not base.metadata.chain:
            return "chain unavailable"
        if base.metadata.transaction_count < 0:
            return "transaction count invalid"
        if not base.metadata.analysis_completeness:
            return "completeness unavailable"
        if base.metadata.scope_type == "unavailable":
            return "scope metadata unavailable"
        if not base.metadata.providers:
            return "provider status unavailable"
        if not base.evidence:
            return "evidence index unavailable"
        if narrative is None:
            return "narrative unavailable"
        if narrative.metadata.fallback_used:
            return "AI provider fallback"
        if not narrative.validation.valid:
            return "AI validation failed"
        sections = self._sections(narrative)
        if len(sections) < self.minimum_section_count:
            return "insufficient AI enrichment sections"
        if fallback_baseline is not None and self._text(narrative) == self._text(
            fallback_baseline
        ):
            return "AI narrative adds no substantive content beyond fallback"
        narrative_text = "\n".join(self._text(narrative))
        if len(narrative_text.strip()) < 240:
            return "AI narrative contains only template-level content"
        if (
            base.metadata.analysis_completeness != "complete"
            and re.search(
                r"完整取得之歷史資料|完整歷史(?:總額|首次|最後|交易數)",
                narrative_text,
            )
        ):
            return "partial scope described as complete"
        if re.search(
            r"(?:確定|證實|認定).{0,8}(?:犯罪|洗錢|詐欺|實際控制人)",
            narrative_text,
        ):
            return "banned certainty wording"
        known_evidence = {item.evidence_id for item in base.evidence}
        known_evidence.update(
            str(record_id)
            for item in base.evidence
            for record_id in item.metadata.get("record_ids", ())
        )
        known_evidence.update(
            match
            for section in base.sections
            for table in section.tables
            for row in table.rows
            for cell in row
            for match in re.findall(r"\b(?:IF|E)\d+\b", str(cell))
        )
        known_facts = self._first_column(base, "investigation_facts")
        known_observations = self._first_column(
            base, "investigation_observations"
        )
        known_facts.update(
            ref for section in base.sections for ref in section.fact_refs
        )
        known_observations.update(
            ref for section in base.sections for ref in section.observation_refs
        )
        source_value = (
            asdict(validation_source)
            if is_dataclass(validation_source)
            else validation_source
        )
        if isinstance(source_value, dict):
            known_facts.update(
                str(item.get("fact_code"))
                for item in source_value.get("conclusion_facts", ())
                if isinstance(item, dict) and item.get("fact_code")
            )
            known_observations.update(
                str(item.get("code"))
                for item in source_value.get("observations", ())
                if isinstance(item, dict) and item.get("code")
            )
        for claim in narrative.claims:
            if not (
                claim.fact_codes
                or claim.observation_ids
                or claim.evidence_ids
            ):
                return f"ungrounded claim: {claim.claim_id}"
            if not set(claim.evidence_ids).issubset(known_evidence):
                return f"unknown evidence reference: {claim.claim_id}"
            if not set(claim.fact_codes).issubset(known_facts):
                return f"unknown fact reference: {claim.claim_id}"
            if not set(claim.observation_ids).issubset(known_observations):
                return f"unknown observation reference: {claim.claim_id}"
            if claim.claim_type == "candidate" and re.search(
                r"(?:已確認|確定|證實).{0,8}(?:交易所|服務商|OTC|支付|控制人)",
                claim.statement,
            ):
                return f"candidate promoted to confirmed: {claim.claim_id}"
        allowed_numbers = set(
            re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", self._base_text(base))
        )
        if source_value is not None:
            allowed_numbers.update(
                re.findall(
                    r"(?<![A-Za-z])\d+(?:\.\d+)?",
                    json.dumps(source_value, ensure_ascii=False, default=str),
                )
            )
        for claim in narrative.claims:
            if not set(claim.numeric_values).issubset(allowed_numbers):
                return f"unknown numeric value: {claim.claim_id}"
        known_identifiers = set(
            re.findall(IDENTIFIER_PATTERN, self._base_text(base))
        )
        for identifier in re.findall(IDENTIFIER_PATTERN, narrative_text):
            if identifier not in known_identifiers:
                return "AI introduced unknown address or transaction identifier"
        return None

    @staticmethod
    def _first_column(document, table_id) -> set[str]:
        return {
            row[0]
            for section in document.sections
            for table in section.tables
            if table.table_id == table_id
            for row in table.rows
            if row
        }

    @staticmethod
    def _text(narrative) -> tuple[str, ...]:
        return tuple(
            paragraph.text.strip()
            for name in AI_SECTION_NAMES
            for section in (getattr(narrative, name, None),)
            if section
            for paragraph in section.paragraphs
        )

    @staticmethod
    def _base_text(document) -> str:
        values = [
            document.title,
            document.conclusion.text,
            document.metadata.target_address or "",
            document.metadata.chain or "",
        ]
        for section in document.sections:
            values.extend(section.content_blocks)
            for table in section.tables:
                values.extend(table.columns)
                values.extend(cell for row in table.rows for cell in row)
        return "\n".join(str(value) for value in values)

    @staticmethod
    def _sections(narrative) -> tuple[ReportSection, ...]:
        result = []
        for index, name in enumerate(AI_SECTION_NAMES, 1):
            section = getattr(narrative, name, None)
            if not section:
                continue
            citations = {
                item.citation_id: item.evidence_id
                for item in narrative.citations
                if item.section in {name, section.section_id}
            }
            refs = tuple(
                dict.fromkeys(
                    citations[citation_id]
                    for paragraph in section.paragraphs
                    for citation_id in paragraph.citation_ids
                    if citation_id in citations
                )
            )
            claims = tuple(
                claim
                for claim in narrative.claims
                if claim.section in {name, section.section_id}
            )
            fact_refs = tuple(
                dict.fromkeys(
                    ref for claim in claims for ref in claim.fact_codes
                )
            )
            observation_refs = tuple(
                dict.fromkeys(
                    ref for claim in claims for ref in claim.observation_ids
                )
            )
            claim_evidence = tuple(
                dict.fromkeys(
                    ref for claim in claims for ref in claim.evidence_ids
                )
            )
            refs = tuple(dict.fromkeys((*refs, *claim_evidence)))
            limitations = tuple(
                ReportLimitation(f"ai_{name}_{number}", redact(text))
                for number, text in enumerate(
                    dict.fromkeys(
                        text for claim in claims for text in claim.limitations
                    ),
                    1,
                )
            )
            epistemic = []
            for claim in claims:
                label = {
                    "factual": "已確認資料事實",
                    "observation": "規則式觀察",
                    "candidate": "候選解釋",
                    "question": "尚待查證",
                    "recommendation": "後續調查建議",
                }.get(claim.claim_type, "候選解釋")
                epistemic.append(f"{label}：{_formalize_ai_text(claim.statement)}")
            result.append(
                ReportSection(
                    section_id=f"ai_{name}",
                    title=f"AI 專業綜合：{redact(section.title)}",
                    order=20 + index,
                    content_blocks=tuple(
                        _formalize_ai_text(paragraph.text)
                        for paragraph in section.paragraphs
                    )
                    + tuple(epistemic),
                    evidence_refs=refs,
                    limitations=limitations,
                    section_type=name,
                    claims=tuple(claim.claim_id for claim in claims),
                    fact_refs=fact_refs,
                    observation_refs=observation_refs,
                    confidence=min(
                        (claim.confidence for claim in claims),
                        default="medium",
                        key={"low": 0, "medium": 1, "high": 2}.get,
                    ),
                    review_status=getattr(
                        narrative.review_status,
                        "value",
                        str(narrative.review_status),
                    ),
                )
            )
        return tuple(result)
