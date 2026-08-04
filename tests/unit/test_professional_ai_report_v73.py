from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import reportlab

from crypto_investigator.ai.fallback import DeterministicFallbackProvider
from crypto_investigator.narratives.models import (
    NarrativeInput,
    NarrativeParagraph,
    NarrativeValidationResult,
)
from crypto_investigator.narratives.sections import DEFAULT_SECTIONS
from crypto_investigator.reports.ai_enrichment import (
    AIReportIntegrator,
    AI_SECTION_NAMES,
    REQUIRED_DETERMINISTIC_SECTIONS,
)
from crypto_investigator.reports.models import (
    ReportConclusion,
    ReportDocument,
    ReportEvidence,
    ReportMetadata,
    ReportSection,
    ReportTable,
)
from crypto_investigator.reports.export import ReportExportCoordinator


def base_report():
    fact_table = ReportTable(
        "investigation_facts",
        "Conclusion Facts",
        ("Fact", "Value"),
        (("transaction_count", "12"),),
    )
    observation_table = ReportTable(
        "investigation_observations",
        "Observations",
        ("Code", "Statement"),
        (("OBS1", "供款來源發生切換"),),
    )
    sections = []
    for order, section_id in enumerate(
        sorted(REQUIRED_DETERMINISTIC_SECTIONS), 1
    ):
        tables = ()
        if section_id == "investigation_facts":
            tables = (fact_table,)
        elif section_id == "investigation_observations":
            tables = (observation_table,)
        sections.append(
            ReportSection(
                section_id,
                section_id,
                order,
                (f"deterministic:{section_id}",),
                tables=tables,
                evidence_refs=("E1",),
            )
        )
    return ReportDocument(
        "Base",
        ReportMetadata(
            "R1",
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            chain="tron",
            target_address="TTarget",
            providers=("trongrid",),
            transaction_count=12,
            analysis_completeness="partial",
            deterministic_section_count=len(sections),
            scope_type="full_history",
            full_history_complete=False,
        ),
        tuple(sections),
        (
            ReportEvidence(
                "E1",
                "artifact",
                "investigation_evidence.json",
                "artifact",
                "structured evidence",
                hash="a" * 64,
            ),
        ),
        (),
        (),
        (),
        ReportConclusion("partial", "deterministic conclusion"),
    )


def narrative_source():
    return NarrativeInput(
        report_metadata={"transaction_count": 12},
        target_address="TTarget",
        chain="tron",
        analysis_period={"from": "2026-01-01", "to": "2026-01-31"},
        completeness="partial",
        provider_limits=(),
        asset_summaries=({"asset": "USDT"},),
        direction_reconciliation={"transaction_count": 12},
        funding_sources=({"address": "TFunder", "rank": 1},),
        outgoing_destinations=({"address": "TOut"},),
        funding_transitions=(),
        operation_stages=(),
        dormancy=(),
        holding_time=(),
        transfer_patterns=(),
        concentration_metrics={},
        counterparty_roles=(),
        label_matches=(),
        observations=({"code": "OBS1"},),
        conclusion_facts=(
            {"fact_code": "transaction_count", "value": 12},
        ),
        limitations=("partial",),
        evidence_index=({"evidence_id": "E1"},),
        requested_sections=DEFAULT_SECTIONS,
    )


def ai_narrative():
    fallback = DeterministicFallbackProvider().generate(narrative_source())
    changes = {}
    for name in DEFAULT_SECTIONS:
        section = getattr(fallback, name)
        changes[name] = replace(
            section,
            paragraphs=(
                NarrativeParagraph(
                    f"跨章節專業綜合：{name}；引用已驗證資料。",
                    ("C1",),
                ),
            ),
        )
    return replace(
        fallback,
        metadata=replace(
            fallback.metadata,
            provider="mock",
            model="professional-fixture",
            status="ai_complete",
            fallback_used=False,
        ),
        validation=NarrativeValidationResult(True, checked_claims=1),
        **changes,
    )


@pytest.mark.parametrize("section_id", sorted(REQUIRED_DETERMINISTIC_SECTIONS))
def test_ai_report_preserves_each_required_deterministic_section(section_id):
    result = AIReportIntegrator().integrate(base_report(), ai_narrative())
    assert section_id in {item.section_id for item in result.sections}


@pytest.mark.parametrize(
    "field,expected",
    (
        ("report_type", "ai_assisted"),
        ("base_report_version", "6"),
        ("ai_enrichment_enabled", True),
        ("ai_provider", "mock"),
        ("ai_model", "professional-fixture"),
        ("validation_status", "passed"),
        ("fallback", False),
        ("fallback_reason", None),
        ("review_status", "not_reviewed"),
        ("ai_section_count", len(AI_SECTION_NAMES)),
    ),
)
def test_ai_report_metadata(field, expected):
    result = AIReportIntegrator().integrate(base_report(), ai_narrative())
    assert getattr(result.metadata, field) == expected


@pytest.mark.parametrize("section_name", AI_SECTION_NAMES)
def test_ai_report_adds_each_professional_section(section_name):
    result = AIReportIntegrator().integrate(base_report(), ai_narrative())
    section = next(
        item for item in result.sections if item.section_id == f"ai_{section_name}"
    )
    assert section.content_blocks
    assert section.title.startswith("AI 專業綜合")


@pytest.mark.parametrize(
    "mutation,reason",
    (
        (
            lambda report, narrative: (report, replace(
                narrative,
                metadata=replace(narrative.metadata, fallback_used=True),
            )),
            "AI provider fallback",
        ),
        (
            lambda report, narrative: (report, replace(
                narrative,
                validation=NarrativeValidationResult(False, ("bad",)),
            )),
            "AI validation failed",
        ),
        (
            lambda report, narrative: (
                replace(report, metadata=replace(report.metadata, target_address=None)),
                narrative,
            ),
            "target address unavailable",
        ),
        (
            lambda report, narrative: (
                replace(report, metadata=replace(report.metadata, chain=None)),
                narrative,
            ),
            "chain unavailable",
        ),
        (
            lambda report, narrative: (
                replace(
                    report,
                    sections=tuple(
                        item
                        for item in report.sections
                        if item.section_id != "provider_status"
                    ),
                ),
                narrative,
            ),
            "missing deterministic sections",
        ),
    ),
)
def test_quality_gate_falls_back_to_complete_base(mutation, reason):
    base = base_report()
    mutated, narrative = mutation(base, ai_narrative())
    result = AIReportIntegrator().integrate(mutated, narrative)
    assert result.metadata.report_type == "fallback"
    assert result.metadata.fallback is True
    assert reason in result.metadata.fallback_reason
    assert not any(item.section_id.startswith("ai_") for item in result.sections)
    assert tuple(
        item.section_id for item in result.sections
    ) == tuple(item.section_id for item in mutated.sections)


def test_unknown_evidence_reference_is_rejected():
    narrative = ai_narrative()
    claim = replace(narrative.claims[0], evidence_ids=("MISSING",))
    result = AIReportIntegrator().integrate(
        base_report(), replace(narrative, claims=(claim,))
    )
    assert result.metadata.fallback is True
    assert "unknown evidence reference" in result.metadata.fallback_reason


def test_ungrounded_claim_is_rejected():
    narrative = ai_narrative()
    claim = replace(
        narrative.claims[0],
        evidence_ids=(),
        fact_codes=(),
        observation_ids=(),
    )
    result = AIReportIntegrator().integrate(
        base_report(), replace(narrative, claims=(claim,))
    )
    assert result.metadata.fallback is True
    assert "ungrounded claim" in result.metadata.fallback_reason


def test_identical_fallback_narrative_is_rejected():
    fallback = DeterministicFallbackProvider().generate(narrative_source())
    mislabeled = replace(
        fallback,
        metadata=replace(fallback.metadata, fallback_used=False),
    )
    result = AIReportIntegrator().integrate(
        base_report(), mislabeled, fallback_baseline=fallback
    )
    assert result.metadata.fallback is True
    assert "no substantive content" in result.metadata.fallback_reason


def test_scope_metadata_is_required():
    base = base_report()
    base = replace(
        base, metadata=replace(base.metadata, scope_type="unavailable")
    )
    result = AIReportIntegrator().integrate(base, ai_narrative())
    assert result.metadata.fallback is True
    assert "scope metadata unavailable" in result.metadata.fallback_reason


def test_partial_scope_cannot_be_described_as_complete_history():
    narrative = ai_narrative()
    section = narrative.executive_summary
    narrative = replace(
        narrative,
        executive_summary=replace(
            section,
            paragraphs=(
                NarrativeParagraph("依完整取得之歷史資料完成研判。" * 20, ("C1",)),
            ),
        ),
    )
    result = AIReportIntegrator().integrate(base_report(), narrative)
    assert result.metadata.fallback is True
    assert "partial scope described as complete" in result.metadata.fallback_reason


def test_banned_certainty_wording_is_rejected():
    narrative = ai_narrative()
    section = narrative.conclusion
    narrative = replace(
        narrative,
        conclusion=replace(
            section,
            paragraphs=(
                NarrativeParagraph("已確定涉及洗錢。" * 30, ("C1",)),
            ),
        ),
    )
    result = AIReportIntegrator().integrate(base_report(), narrative)
    assert result.metadata.fallback is True
    assert "banned certainty wording" in result.metadata.fallback_reason


def test_unknown_numeric_value_is_rejected():
    narrative = ai_narrative()
    claim = replace(narrative.claims[0], numeric_values=("999999",))
    result = AIReportIntegrator().integrate(
        base_report(), replace(narrative, claims=(claim, *narrative.claims[1:]))
    )
    assert result.metadata.fallback is True
    assert "unknown numeric value" in result.metadata.fallback_reason


def test_unknown_address_is_rejected():
    narrative = ai_narrative()
    section = narrative.executive_summary
    narrative = replace(
        narrative,
        executive_summary=replace(
            section,
            paragraphs=(
                NarrativeParagraph(
                    "未知地址 TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE 被加入報告。" * 8,
                    ("C1",),
                ),
            ),
        ),
    )
    result = AIReportIntegrator().integrate(base_report(), narrative)
    assert result.metadata.fallback is True
    assert "unknown address" in result.metadata.fallback_reason


def test_ai_section_keeps_structured_grounding_metadata():
    result = AIReportIntegrator().integrate(base_report(), ai_narrative())
    section = next(
        item for item in result.sections if item.section_id == "ai_executive_summary"
    )
    assert section.section_type == "executive_summary"
    assert section.review_status == "not_reviewed"
    assert section.confidence in {"low", "medium", "high"}
    assert isinstance(section.claims, tuple)
    assert isinstance(section.fact_refs, tuple)
    assert isinstance(section.observation_refs, tuple)
    assert isinstance(section.evidence_refs, tuple)


def test_ai_assisted_full_report_exports_four_formats(tmp_path, monkeypatch):
    document = AIReportIntegrator().integrate(base_report(), ai_narrative())
    font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    monkeypatch.setenv("CHAINSHERLOCK_PDF_CJK_FONT", str(font))
    result = ReportExportCoordinator().export(document, tmp_path, "all")
    assert result.status == "complete"
    assert {
        "report.md",
        "report.html",
        "report.docx",
        "report.pdf",
    }.issubset({item.name for item in tmp_path.iterdir()})
