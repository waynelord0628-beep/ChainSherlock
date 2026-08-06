from decimal import Decimal

from crypto_investigator.domain.investigation_priority import (
    PrioritySignals,
    PriorityTier,
    rank_investigation_priorities,
    score_investigation_priority,
)


def test_priority_score_is_investigative_not_risk_language():
    item = score_investigation_priority(
        candidate_id="C-1",
        address="A",
        asset="USDT",
        signals=PrioritySignals(exclusive_amount_ratio=Decimal("1")),
    )
    assert "risk" not in str(item.to_dict()).lower()
    assert "犯罪" not in str(item.to_dict())


def test_strong_grounded_candidate_is_p1():
    item = score_investigation_priority(
        candidate_id="C-1",
        address="A",
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
    )
    assert item.tier is PriorityTier.P1


def test_deeper_hops_reduce_priority():
    shallow = score_investigation_priority(
        candidate_id="C-1",
        address="A",
        asset="USDT",
        signals=PrioritySignals(exclusive_amount_ratio=Decimal("1"), hop_depth=1),
    )
    deep = score_investigation_priority(
        candidate_id="C-2",
        address="B",
        asset="USDT",
        signals=PrioritySignals(exclusive_amount_ratio=Decimal("1"), hop_depth=4),
    )
    assert shallow.score > deep.score


def test_incomplete_provider_adds_limitation():
    item = score_investigation_priority(
        candidate_id="C-1",
        address="A",
        asset="USDT",
        signals=PrioritySignals(provider_completeness=Decimal("0.5")),
    )
    assert any("Provider" in value for value in item.limitations)


def test_rank_is_deterministic():
    rows = (
        ("C-2", "B", "USDT", PrioritySignals(exclusive_amount_ratio=Decimal("0.2"))),
        ("C-1", "A", "USDT", PrioritySignals(exclusive_amount_ratio=Decimal("0.9"))),
    )
    assert [item.candidate_id for item in rank_investigation_priorities(rows)] == [
        "C-1",
        "C-2",
    ]


def test_invalid_signal_is_rejected():
    try:
        PrioritySignals(fan_out_ratio=Decimal("1.1"))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid ratio must be rejected")
