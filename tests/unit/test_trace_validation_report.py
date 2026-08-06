from decimal import Decimal

from crypto_investigator.domain.investigation_priority import (
    PrioritySignals,
    score_investigation_priority,
)
from crypto_investigator.domain.trace_accounting import reconcile_branch
from crypto_investigator.reports.trace_validation import (
    compose_trace_validation_casebook,
    compose_trace_validation_dossiers,
)
from crypto_investigator.reports.export import ReportExportCoordinator
from tests.unit.test_trace_evidence_package import _result


def test_casebook_contains_main_and_technical_sections():
    result = _result()
    conservation = (
        reconcile_branch(
            branch_id="B-1",
            asset="USDT",
            first_hop_received=Decimal("10.25"),
            retained=Decimal("10.25"),
        ),
    )
    priority = (
        score_investigation_priority(
            candidate_id="C-1",
            address="NEXT",
            asset="USDT",
            signals=PrioritySignals(exclusive_amount_ratio=Decimal("1")),
        ),
    )
    casebook = compose_trace_validation_casebook(
        result, conservation=conservation, priorities=priority
    )
    assert casebook.metadata.report_type == "deterministic_multihop_casebook"
    section_ids = [item.section_id for item in casebook.sections]
    assert "executive_summary" in section_ids
    assert "technical_appendix" in section_ids
    assert section_ids.index("executive_summary") < section_ids.index(
        "technical_appendix"
    )
    assert compose_trace_validation_dossiers(
        result, conservation=conservation, priorities=priority
    ).title == casebook.title


def test_main_report_explains_shared_cap_is_not_total():
    main = compose_trace_validation_casebook(
        _result(), conservation=(), priorities=()
    )
    text = "\n".join(
        block for section in main.sections for block in section.content_blocks
    )
    assert "共享上限" in text
    assert "不得重複加總" in text


def test_main_report_avoids_confirmed_identity_claim():
    main = compose_trace_validation_casebook(
        _result(), conservation=(), priorities=()
    )
    text = repr(main)
    assert "不等於已確認交易所" in text
    assert "已確認犯罪" not in text


def test_casebook_main_summary_has_required_amounts_and_evidence_ids():
    result = _result()
    conservation = (
        reconcile_branch(
            branch_id="BRANCH-EVIDENCE-001",
            asset="USDT",
            first_hop_received=Decimal("100"),
            retained=Decimal("70"),
            provider_unresolved=Decimal("20"),
            unclassified=Decimal("10"),
        ),
    )
    priority = (
        score_investigation_priority(
            candidate_id="CAND-0001",
            address="NEXT",
            asset="USDT",
            signals=PrioritySignals(
                exclusive_amount_ratio=Decimal("1"),
                first_hop_amount_ratio=Decimal("1"),
                transaction_activity=Decimal("1"),
                aggregation_ratio=Decimal("1"),
                fan_out_ratio=Decimal("1"),
                onward_speed_ratio=Decimal("1"),
                repeated_amount_ratio=Decimal("1"),
                branch_presence_ratio=Decimal("1"),
                label_confidence=Decimal("1"),
                evidence_quality=Decimal("1"),
            ),
        ),
    )
    casebook = compose_trace_validation_casebook(
        result, conservation=conservation, priorities=priority
    )
    summary = next(
        item for item in casebook.sections if item.section_id == "executive_summary"
    )
    summary_text = " ".join(summary.content_blocks)
    assert "第一層總流出金額：100" in summary_text
    assert "尚未分類：10（10.00%）" in summary_text
    assert "Provider 未解決：20" in summary_text
    assert "BRANCH-EVIDENCE-001" in summary.evidence_refs
    p1 = next(item for item in casebook.sections if item.section_id == "p1_tasks")
    assert "CAND-0001" in p1.evidence_refs


def test_casebook_default_technical_paths_are_bounded():
    casebook = compose_trace_validation_casebook(
        _result(), conservation=(), priorities=()
    )
    paths = next(
        item for item in casebook.sections if item.section_id == "technical_paths"
    )
    assert len(paths.tables[0].rows) <= 30


def test_casebook_body_avoids_engineering_terms():
    casebook = compose_trace_validation_casebook(
        _result(), conservation=(), priorities=()
    )
    main_text = repr(casebook.sections[:14])
    for term in ("accounting conservation", "bottleneck upper bound", "evidence gate"):
        assert term not in main_text


def test_casebook_exports_one_pdf_with_main_and_appendix_bookmarks(tmp_path):
    casebook = compose_trace_validation_casebook(
        _result(), conservation=(), priorities=()
    )
    exported = ReportExportCoordinator().export(casebook, tmp_path, "all")
    assert exported.status in {"complete", "partial"}
    assert len(tuple(tmp_path.glob("*.pdf"))) == 1
    for filename in ("report.md", "report.html", "report.docx", "report.pdf"):
        assert (tmp_path / filename).is_file()
    pdf_bytes = (tmp_path / "report.pdf").read_bytes()
    assert b"/Outlines" in pdf_bytes
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert markdown.index("執行摘要") < markdown.index("第二部　技術驗證附錄")
