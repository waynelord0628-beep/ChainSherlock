from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import re
from typing import Mapping

from crypto_investigator.domain.transaction import Transaction, TransactionType


class TronTransferClassification(StrEnum):
    NORMAL_VALUE_TRANSFER = "normal_value_transfer"
    FEE_OR_ACCOUNT_ACTIVATION = "fee_or_account_activation"
    RESOURCE_RELATED = "resource_related"
    CONTRACT_RELATED = "contract_related"
    SYSTEM_OR_REWARD = "system_or_reward"
    PROMOTIONAL_CANDIDATE = "promotional_candidate"
    DUSTING_CANDIDATE = "dusting_candidate"
    PHISHING_CANDIDATE = "phishing_candidate"
    UNCLASSIFIED = "unclassified"


class HumanReviewStatus(StrEnum):
    NOT_REVIEWED = "not_reviewed"
    ACCEPTED_AS_EXCLUDED = "accepted_as_excluded"
    REJECTED_EXCLUSION = "rejected_exclusion"
    CONFIRMED_BY_EXTERNAL_LABEL = "confirmed_by_external_label"


@dataclass(frozen=True, slots=True)
class TronTransferSignals:
    sender_outbound_recipient_count: int | None = None
    same_amount_recipient_count: int | None = None
    same_amount_source_count: int | None = None
    memo_or_data: str | None = None
    external_label: str | None = None
    prior_interaction: bool | None = None
    subsequent_material_use: bool | None = None


@dataclass(frozen=True, slots=True)
class TronTransferAssessment:
    txid: str
    block: int | None
    timestamp: datetime | None
    sender: str | None
    receiver: str | None
    contract_type: str
    raw_amount: str
    normalized_amount: Decimal
    success: bool | None
    memo_or_data: str | None
    sender_outbound_recipient_count: int | None
    same_amount_recipient_count: int | None
    same_amount_frequency: int | None
    external_label_status: str | None
    classification: TronTransferClassification
    reason_codes: tuple[str, ...]
    confidence: str
    source_evidence: tuple[str, ...]
    human_review_status: HumanReviewStatus
    included_in_fund_flow: bool
    reversible: bool = True


_PROMOTIONAL_TERMS = re.compile(
    r"(https?://|www\.|telegram|t\.me|claim|reward|airdrop|bonus|"
    r"wallet\s*validation|connect\s*wallet|approval)",
    re.IGNORECASE,
)
_PHISHING_LABELS = {"phishing", "scam", "advertising", "dusting"}
_RESOURCE_CONTRACTS = {
    "FreezeBalanceContract",
    "UnfreezeBalanceContract",
    "DelegateResourceContract",
    "UnDelegateResourceContract",
    "VoteWitnessContract",
}
_SYSTEM_CONTRACTS = {"WithdrawBalanceContract", "AccountCreateContract"}


def classify_tron_transfer(
    transaction: Transaction,
    signals: TronTransferSignals = TronTransferSignals(),
    *,
    evidence_refs: tuple[str, ...] = (),
) -> TronTransferAssessment:
    """Classify a TRON transfer without mutating or deleting source evidence."""
    amount = transaction.amount or Decimal(0)
    metadata: Mapping[str, object] = transaction.metadata or {}
    contract_type = str(metadata.get("contract_type") or transaction.transaction_type.value)
    memo = signals.memo_or_data or str(
        metadata.get("memo") or metadata.get("data") or ""
    ) or None
    reasons = []

    if transaction.success is False:
        classification = TronTransferClassification.UNCLASSIFIED
        reasons.append("transaction_failed")
        included = False
        confidence = "high"
    elif contract_type in _RESOURCE_CONTRACTS:
        classification = TronTransferClassification.RESOURCE_RELATED
        reasons.append("resource_contract")
        included = False
        confidence = "high"
    elif contract_type in _SYSTEM_CONTRACTS:
        classification = TronTransferClassification.SYSTEM_OR_REWARD
        reasons.append("system_or_reward_contract")
        included = False
        confidence = "high"
    elif (
        contract_type != "TransferContract"
        or transaction.asset_symbol != "TRX"
        or transaction.transaction_type is not TransactionType.NATIVE_TRANSFER
    ):
        classification = TronTransferClassification.CONTRACT_RELATED
        reasons.append("not_native_trx_transfer")
        included = False
        confidence = "high"
    else:
        if (signals.same_amount_source_count or 0) >= 2:
            reasons.append("same_amount_multiple_sources")
        if (signals.same_amount_recipient_count or 0) >= 20:
            reasons.append("same_amount_high_fanout")
        if (signals.sender_outbound_recipient_count or 0) >= 100:
            reasons.append("sender_high_fanout")
        if memo and _PROMOTIONAL_TERMS.search(memo):
            reasons.append("promotional_or_phishing_text")
        label = (signals.external_label or "").casefold()
        if label in _PHISHING_LABELS:
            reasons.append("trusted_external_label")
        if signals.prior_interaction is False:
            reasons.append("no_prior_interaction")
        if signals.subsequent_material_use is False:
            reasons.append("no_subsequent_material_use")

        if "trusted_external_label" in reasons:
            classification = TronTransferClassification.PHISHING_CANDIDATE
            included = False
            confidence = "high"
        elif "promotional_or_phishing_text" in reasons and len(reasons) >= 2:
            classification = TronTransferClassification.PHISHING_CANDIDATE
            included = False
            confidence = "medium"
        elif any(
            code in reasons
            for code in ("same_amount_high_fanout", "sender_high_fanout")
        ):
            classification = TronTransferClassification.PROMOTIONAL_CANDIDATE
            included = False
            confidence = "medium"
        elif amount and amount < Decimal("0.01") and len(reasons) >= 2:
            classification = TronTransferClassification.DUSTING_CANDIDATE
            included = False
            confidence = "medium"
        elif reasons:
            classification = TronTransferClassification.PROMOTIONAL_CANDIDATE
            included = True
            confidence = "low"
        else:
            classification = TronTransferClassification.NORMAL_VALUE_TRANSFER
            included = True
            confidence = "medium"

    review = (
        HumanReviewStatus.CONFIRMED_BY_EXTERNAL_LABEL
        if "trusted_external_label" in reasons
        else HumanReviewStatus.NOT_REVIEWED
    )
    return TronTransferAssessment(
        txid=transaction.tx_hash,
        block=transaction.block_number,
        timestamp=transaction.timestamp,
        sender=transaction.from_address,
        receiver=transaction.to_address,
        contract_type=contract_type,
        raw_amount=str(transaction.amount or "0"),
        normalized_amount=amount,
        success=transaction.success,
        memo_or_data=memo,
        sender_outbound_recipient_count=signals.sender_outbound_recipient_count,
        same_amount_recipient_count=signals.same_amount_recipient_count,
        same_amount_frequency=signals.same_amount_source_count,
        external_label_status=signals.external_label,
        classification=classification,
        reason_codes=tuple(reasons),
        confidence=confidence,
        source_evidence=evidence_refs,
        human_review_status=review,
        included_in_fund_flow=included,
    )


def apply_human_review(
    assessment: TronTransferAssessment,
    status: HumanReviewStatus,
) -> TronTransferAssessment:
    if status is HumanReviewStatus.ACCEPTED_AS_EXCLUDED:
        return replace(
            assessment,
            human_review_status=status,
            included_in_fund_flow=False,
        )
    if status is HumanReviewStatus.REJECTED_EXCLUSION:
        return replace(
            assessment,
            human_review_status=status,
            included_in_fund_flow=True,
        )
    return replace(assessment, human_review_status=status)
