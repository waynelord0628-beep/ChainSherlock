from datetime import UTC, datetime
from decimal import Decimal

from crypto_investigator.domain.metadata import Metadata
from crypto_investigator.domain.transaction import (
    Chain,
    Direction,
    Transaction,
    TransactionType,
)
from crypto_investigator.investigation.tron_transfers import (
    HumanReviewStatus,
    TronTransferClassification,
    TronTransferSignals,
    apply_human_review,
    classify_tron_transfer,
)


def transaction(amount="8888.88", *, metadata=None, success=True):
    return Transaction(
        chain=Chain.TRON,
        tx_hash="tx-001",
        from_address="TFrom1111111111111111111111111111",
        to_address="TTarget11111111111111111111111111",
        asset_symbol="TRX",
        amount=Decimal(amount),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        success=success,
        transaction_type=TransactionType.NATIVE_TRANSFER,
        direction=Direction.INCOMING,
        metadata=Metadata(metadata or {"contract_type": "TransferContract"}),
    )


def test_8888_amount_alone_is_not_confirmed_phishing():
    result = classify_tron_transfer(transaction())
    assert result.classification is TronTransferClassification.PROMOTIONAL_CANDIDATE
    assert result.confidence == "low"
    assert result.included_in_fund_flow is True


def test_same_amount_multiple_sources_quarantines_candidate():
    result = classify_tron_transfer(
        transaction(),
        TronTransferSignals(same_amount_source_count=2),
    )
    assert result.classification is TronTransferClassification.PROMOTIONAL_CANDIDATE
    assert result.included_in_fund_flow is False
    assert "same_amount_multiple_sources" in result.reason_codes


def test_high_fanout_increases_suspicious_signals():
    result = classify_tron_transfer(
        transaction(),
        TronTransferSignals(
            sender_outbound_recipient_count=120,
            same_amount_recipient_count=30,
        ),
    )
    assert "sender_high_fanout" in result.reason_codes
    assert "same_amount_high_fanout" in result.reason_codes
    assert result.included_in_fund_flow is False


def test_url_memo_adds_promotional_or_phishing_signal():
    result = classify_tron_transfer(
        transaction(),
        TronTransferSignals(memo_or_data="https://example.invalid claim reward"),
    )
    assert "promotional_or_phishing_text" in result.reason_codes
    assert result.classification is TronTransferClassification.PHISHING_CANDIDATE


def test_resource_contract_is_excluded_from_material_flow():
    result = classify_tron_transfer(
        transaction(metadata={"contract_type": "DelegateResourceContract"})
    )
    assert result.classification is TronTransferClassification.RESOURCE_RELATED
    assert result.included_in_fund_flow is False


def test_failed_transaction_is_not_material_flow():
    result = classify_tron_transfer(transaction(success=False))
    assert result.classification is TronTransferClassification.UNCLASSIFIED
    assert result.included_in_fund_flow is False


def test_human_can_accept_exclusion_without_mutating_source_assessment():
    original = classify_tron_transfer(transaction())
    reviewed = apply_human_review(
        original, HumanReviewStatus.ACCEPTED_AS_EXCLUDED
    )
    assert original.included_in_fund_flow is True
    assert reviewed.included_in_fund_flow is False
    assert reviewed.human_review_status is HumanReviewStatus.ACCEPTED_AS_EXCLUDED


def test_human_can_reject_and_reverse_exclusion():
    original = classify_tron_transfer(
        transaction(),
        TronTransferSignals(same_amount_source_count=2),
    )
    reviewed = apply_human_review(
        original, HumanReviewStatus.REJECTED_EXCLUSION
    )
    assert reviewed.included_in_fund_flow is True
    assert reviewed.reversible is True


def test_external_label_is_preserved_as_candidate_not_crime_conclusion():
    result = classify_tron_transfer(
        transaction(),
        TronTransferSignals(external_label="phishing"),
    )
    assert result.classification is TronTransferClassification.PHISHING_CANDIDATE
    assert result.human_review_status is HumanReviewStatus.CONFIRMED_BY_EXTERNAL_LABEL
    assert "crime" not in " ".join(result.reason_codes)
