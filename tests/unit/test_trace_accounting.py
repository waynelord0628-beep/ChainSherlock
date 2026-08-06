from decimal import Decimal

import pytest

from crypto_investigator.domain.trace_accounting import (
    AmountStatus,
    PathAllocation,
    PathAllocationType,
    classify_legacy_path_amount,
    reconcile_branch,
    reconcile_case,
)


def _exclusive(path_id: str, amount: str) -> PathAllocation:
    return PathAllocation(
        path_id=path_id,
        allocation_type=PathAllocationType.EXCLUSIVE,
        amount_status=AmountStatus.KNOWN_AMOUNT,
        exclusive_amount=Decimal(amount),
        confidence=Decimal("1"),
        accounting_eligible=True,
        evidence_refs=(f"EVIDENCE-{path_id}",),
    )


def _shared(path_id: str, amount: str, group: str) -> PathAllocation:
    return PathAllocation(
        path_id=path_id,
        allocation_type=PathAllocationType.SHARED_CAP,
        amount_status=AmountStatus.KNOWN_AMOUNT,
        shared_cap=Decimal(amount),
        shared_group_id=group,
        confidence=Decimal("0.7"),
        evidence_refs=(f"EVIDENCE-{path_id}",),
    )


def test_branch_conservation_excludes_shared_cap_from_accounted_total():
    result = reconcile_branch(
        branch_id="BRANCH-001",
        asset="USDT",
        first_hop_received=Decimal("100"),
        allocations=(
            _exclusive("PATH-001", "60"),
            _shared("PATH-002", "90", "SHARED-001"),
            _shared("PATH-003", "90", "SHARED-001"),
        ),
        pruned=Decimal("10"),
        retained=Decimal("20"),
        below_threshold=Decimal("5"),
        provider_unresolved=Decimal("5"),
    )
    assert result.conserved
    assert result.accounted_total == Decimal("100")
    assert result.allocated_unique == Decimal("60")
    assert result.shared_cap_total == Decimal("90")
    assert result.delta == Decimal("0")


def test_shared_group_with_conflicting_caps_is_rejected():
    with pytest.raises(ValueError, match="conflicting caps"):
        reconcile_branch(
            branch_id="BRANCH-001",
            asset="USDT",
            first_hop_received=Decimal("100"),
            allocations=(
                _shared("PATH-001", "90", "SHARED-001"),
                _shared("PATH-002", "80", "SHARED-001"),
            ),
            unclassified=Decimal("100"),
        )


def test_unknown_or_unavailable_amount_cannot_carry_zero_placeholder():
    with pytest.raises(ValueError, match="cannot carry a value"):
        PathAllocation(
            path_id="PATH-UNKNOWN",
            allocation_type=PathAllocationType.UNALLOCATED,
            amount_status=AmountStatus.UNAVAILABLE_AMOUNT,
            exclusive_amount=Decimal("0"),
        )


def test_legacy_zero_without_edge_evidence_is_unavailable_not_zero():
    assert classify_legacy_path_amount(
        raw_amount=Decimal("0"),
        has_edge_evidence=False,
    ) is AmountStatus.UNAVAILABLE_AMOUNT


def test_explicit_zero_event_requires_edge_evidence():
    assert classify_legacy_path_amount(
        raw_amount=Decimal("0"),
        has_edge_evidence=True,
        explicit_zero_value_event=True,
    ) is AmountStatus.ZERO_VALUE_EVENT
    assert classify_legacy_path_amount(
        raw_amount=Decimal("0"),
        has_edge_evidence=False,
        explicit_zero_value_event=True,
    ) is AmountStatus.UNAVAILABLE_AMOUNT


def test_nonzero_legacy_amount_is_known():
    assert classify_legacy_path_amount(
        raw_amount=Decimal("90000"),
        has_edge_evidence=True,
    ) is AmountStatus.KNOWN_AMOUNT


def test_unbalanced_branch_reports_delta_instead_of_silently_passing():
    result = reconcile_branch(
        branch_id="BRANCH-UNBALANCED",
        asset="USDT",
        first_hop_received=Decimal("100"),
        allocations=(_exclusive("PATH-001", "60"),),
    )
    assert not result.conserved
    assert result.delta == Decimal("40")


def test_decimal_tolerance_is_explicit():
    result = reconcile_branch(
        branch_id="BRANCH-TOLERANCE",
        asset="USDT",
        first_hop_received=Decimal("1"),
        allocations=(_exclusive("PATH-001", "0.9999995"),),
        tolerance=Decimal("0.000001"),
    )
    assert result.conserved
    assert result.delta == Decimal("0.0000005")


def test_case_conservation_keeps_shared_caps_out_of_resolved_amount():
    first = reconcile_branch(
        branch_id="BRANCH-001",
        asset="USDT",
        first_hop_received=Decimal("100"),
        allocations=(_exclusive("PATH-001", "70"), _shared("S1", "50", "G1")),
        retained=Decimal("30"),
    )
    second = reconcile_branch(
        branch_id="BRANCH-002",
        asset="USDT",
        first_hop_received=Decimal("50"),
        allocations=(_exclusive("PATH-002", "25"),),
        unclassified=Decimal("25"),
    )
    result = reconcile_case((first, second))
    assert result.conserved
    assert result.first_hop_received == Decimal("150")
    assert result.accounted_total == Decimal("150")
    assert result.shared_cap_total == Decimal("50")
    assert result.unresolved_amount == Decimal("25")


def test_case_conservation_refuses_cross_asset_addition():
    usdt = reconcile_branch(
        branch_id="USDT",
        asset="USDT",
        first_hop_received=Decimal("1"),
        retained=Decimal("1"),
    )
    trx = reconcile_branch(
        branch_id="TRX",
        asset="TRX",
        first_hop_received=Decimal("1"),
        retained=Decimal("1"),
    )
    with pytest.raises(ValueError, match="different assets"):
        reconcile_case((usdt, trx))
