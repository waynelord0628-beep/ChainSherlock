"""Evidence-backed off-ramp candidate construction from local label records."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from crypto_investigator.domain.fund_tracing import (
    OffRampCandidate,
    StopCondition,
    StopConditionType,
    TraceEdge,
)


class LabelLookup(Protocol):
    def check(self, chain: str, address: str) -> tuple[Any, ...]: ...


_SUPPORTED_CATEGORIES = {
    "exchange",
    "vasp",
    "otc",
    "payment",
    "service",
    "bridge",
    "mixer",
}
_TRUSTED_STATUSES = {"manual_confirmed", "trusted_local", "provider_label"}


def detect_off_ramps(
    *,
    chain: str,
    edges: tuple[TraceEdge, ...],
    labels: LabelLookup,
) -> tuple[tuple[OffRampCandidate, ...], tuple[StopCondition, ...]]:
    """Build candidates; only trusted exchange/VASP labels are confirmed stops."""

    receipts: dict[tuple[str, str], list[TraceEdge]] = defaultdict(list)
    for edge in edges:
        receipts[(edge.to_address, edge.asset)].append(edge)

    candidates = []
    stops = []
    for (address, asset), related in sorted(receipts.items()):
        matches = tuple(
            label
            for label in labels.check(chain, address)
            if getattr(label, "category", "unknown") in _SUPPORTED_CATEGORIES
        )
        if not matches:
            continue
        label = matches[0]
        verification = getattr(label, "verification_status", "unverified_candidate")
        trusted = verification in _TRUSTED_STATUSES
        category = getattr(label, "category", "unknown")
        evidence = tuple(
            dict.fromkeys(ref for edge in related for ref in edge.evidence_refs)
        )
        first = min(edge.timestamp for edge in related)
        last = max(edge.timestamp for edge in related)
        candidates.append(
            OffRampCandidate(
                address=address,
                label=getattr(label, "label", None) or None,
                label_source=getattr(label, "source", None) or None,
                asset=asset,
                received_amount=sum((edge.amount for edge in related), Decimal("0")),
                transaction_count=len(related),
                first_receipt=first,
                last_receipt=last,
                subsequent_behavior=f"{category} label; verification={verification}",
                confidence=Decimal("0.9") if trusted else Decimal("0.55"),
                evidence_refs=evidence,
                recommended_action=(
                    "Preserve transaction evidence and verify account ownership records."
                    if trusted
                    else "Verify the candidate label before legal or investigative action."
                ),
                limitations=(
                    ()
                    if trusted
                    else ("Label is not confirmed; off-ramp identity remains a candidate.",)
                ),
                category=category,
            )
        )
        if trusted:
            stop_type = _stop_type(category)
            stops.append(
                StopCondition(
                    condition=stop_type,
                    reason=f"Trusted {category} label matched at {address}",
                    evidence_refs=evidence,
                    reached=True,
                )
            )
    return tuple(candidates), tuple(stops)


def _stop_type(category: str) -> StopConditionType:
    return {
        "exchange": StopConditionType.CONFIRMED_EXCHANGE_OR_VASP,
        "vasp": StopConditionType.CONFIRMED_EXCHANGE_OR_VASP,
        "payment": StopConditionType.PAYMENT_SERVICE,
        "otc": StopConditionType.OTC_CANDIDATE,
        "mixer": StopConditionType.MIXER,
        "bridge": StopConditionType.BRIDGE,
        "service": StopConditionType.PAYMENT_SERVICE,
    }[category]
