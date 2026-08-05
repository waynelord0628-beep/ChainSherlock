from datetime import UTC, datetime
from decimal import Decimal

import pytest

from crypto_investigator.domain.fund_tracing import (
    AllocationMethod,
    OffRampCandidate,
    StopCondition,
    StopConditionType,
    TraceEdge,
)


NOW = datetime(2026, 8, 5, tzinfo=UTC)


def test_stop_condition_is_publicly_serializable():
    condition = StopCondition(
        condition=StopConditionType.PROVIDER_INCOMPLETE,
        reason="required capability pagination is incomplete",
        evidence_refs=("EVIDENCE-PROVIDER-001",),
        reached=True,
    )
    assert condition.to_dict() == {
        "condition": "provider_incomplete",
        "reason": "required capability pagination is incomplete",
        "evidence_refs": ["EVIDENCE-PROVIDER-001"],
        "reached": True,
    }


def test_trace_edge_requires_real_transaction_hash_and_evidence():
    with pytest.raises(ValueError, match="transaction hash"):
        TraceEdge(
            edge_id="EDGE-001",
            from_address="from",
            to_address="to",
            transaction_hash="",
            asset="TRX",
            amount=Decimal("1"),
            timestamp=NOW,
            allocation_method=AllocationMethod.DIRECT_TRANSACTION,
            confidence=Decimal("1"),
            evidence_refs=("EVIDENCE-001",),
        )

    with pytest.raises(ValueError, match="evidence"):
        TraceEdge(
            edge_id="EDGE-001",
            from_address="from",
            to_address="to",
            transaction_hash="real_tx_hash",
            asset="TRX",
            amount=Decimal("1"),
            timestamp=NOW,
            allocation_method=AllocationMethod.DIRECT_TRANSACTION,
            confidence=Decimal("1"),
            evidence_refs=(),
        )


def test_trace_edge_keeps_assets_separate():
    trx = TraceEdge(
        edge_id="EDGE-TRX",
        from_address="from",
        to_address="to",
        transaction_hash="trx_hash",
        asset="TRX",
        amount=Decimal("1"),
        timestamp=NOW,
        allocation_method=AllocationMethod.DIRECT_TRANSACTION,
        confidence=Decimal("1"),
        evidence_refs=("EVIDENCE-TRX",),
    )
    usdt = TraceEdge(
        edge_id="EDGE-USDT",
        from_address="from",
        to_address="to",
        transaction_hash="usdt_hash",
        asset="USDT",
        amount=Decimal("1"),
        timestamp=NOW,
        allocation_method=AllocationMethod.DIRECT_TRANSACTION,
        confidence=Decimal("1"),
        evidence_refs=("EVIDENCE-USDT",),
    )
    assert trx.to_dict()["asset"] == "TRX"
    assert usdt.to_dict()["asset"] == "USDT"


def test_off_ramp_candidate_requires_evidence_and_confidence():
    candidate = OffRampCandidate(
        address="TAddress",
        label="VASP candidate",
        label_source="local_label.csv",
        asset="TRX",
        received_amount=Decimal("100"),
        transaction_count=2,
        first_receipt=NOW,
        last_receipt=NOW,
        subsequent_behavior="awaiting next-hop verification",
        confidence=Decimal("0.6"),
        evidence_refs=("EVIDENCE-001",),
        recommended_action="verify label before requesting records",
    )
    payload = candidate.to_dict()
    assert payload["confidence"] == "0.6"
    assert payload["evidence_refs"] == ["EVIDENCE-001"]

    with pytest.raises(ValueError, match="evidence"):
        OffRampCandidate(
            address="TAddress",
            label=None,
            label_source=None,
            asset="TRX",
            received_amount=Decimal("100"),
            transaction_count=2,
            first_receipt=NOW,
            last_receipt=NOW,
            subsequent_behavior="unknown",
            confidence=Decimal("0.5"),
            evidence_refs=(),
            recommended_action="manual review",
        )
