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


def detect_behavioral_endpoints(
    *,
    edges: tuple[TraceEdge, ...],
    excluded_addresses: frozenset[str] = frozenset(),
    limit: int = 10,
) -> tuple[OffRampCandidate, ...]:
    """Return low-confidence endpoint candidates without asserting identity."""

    incoming: dict[str, list[TraceEdge]] = defaultdict(list)
    outgoing: dict[str, list[TraceEdge]] = defaultdict(list)
    for edge in edges:
        incoming[edge.to_address].append(edge)
        outgoing[edge.from_address].append(edge)
    ranked = []
    for address, receipts in incoming.items():
        if address in excluded_addresses or outgoing.get(address):
            continue
        by_asset: dict[str, list[TraceEdge]] = defaultdict(list)
        for edge in receipts:
            by_asset[edge.asset].append(edge)
        for asset, related in by_asset.items():
            total = sum((edge.amount for edge in related), Decimal("0"))
            ranked.append((total, address, asset, related))
    output = []
    for total, address, asset, related in sorted(
        ranked, key=lambda item: (-item[0], item[1], item[2])
    )[: max(0, limit)]:
        evidence = tuple(
            dict.fromkeys(ref for edge in related for ref in edge.evidence_refs)
        )
        output.append(
            OffRampCandidate(
                address=address,
                label=None,
                label_source=None,
                asset=asset,
                received_amount=total,
                transaction_count=len(related),
                first_receipt=min(edge.timestamp for edge in related),
                last_receipt=max(edge.timestamp for edge in related),
                subsequent_behavior=(
                    "No material outgoing edge was observed within the bounded trace."
                ),
                confidence=Decimal("0.30"),
                evidence_refs=evidence,
                recommended_action=(
                    "Continue the next hop and verify Local Labels before treating "
                    "this endpoint as a service or off-ramp."
                ),
                limitations=(
                    "Behavioral endpoint only; identity and off-ramp status are unconfirmed.",
                    "Provider pagination, materiality, depth, or branch limits may hide outgoing activity.",
                ),
                category="unlabeled_terminal_candidate",
            )
        )
    return tuple(output)


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
