from decimal import Decimal

from crypto_investigator.domain.investigation_priority import (
    PrioritySignals,
    score_investigation_priority,
)
from crypto_investigator.domain.trace_accounting import reconcile_branch
from crypto_investigator.reports.trace_validation import (
    compose_trace_validation_dossiers,
)
from tests.unit.test_trace_evidence_package import _result


def test_main_and_technical_dossiers_are_distinct():
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
    main, technical = compose_trace_validation_dossiers(
        result, conservation=conservation, priorities=priority
    )
    assert main.metadata.report_type == "deterministic_multihop_investigation"
    assert technical.metadata.report_type == "deterministic_multihop_technical_appendix"
    assert {item.section_id for item in main.sections} != {
        item.section_id for item in technical.sections
    }


def test_main_report_explains_shared_cap_is_not_total():
    main, _ = compose_trace_validation_dossiers(
        _result(), conservation=(), priorities=()
    )
    text = "\n".join(
        block for section in main.sections for block in section.content_blocks
    )
    assert "共享上限" in text
    assert "不得重複加總" in text


def test_main_report_avoids_confirmed_identity_claim():
    main, _ = compose_trace_validation_dossiers(
        _result(), conservation=(), priorities=()
    )
    text = repr(main)
    assert "不等於已確認交易所" in text
    assert "已確認犯罪" not in text
