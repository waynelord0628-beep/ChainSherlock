"""Convert normalized provider records into evidence-backed trace edges."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from crypto_investigator.domain.fund_tracing import AllocationMethod, TraceEdge
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.models import ProviderRawRecord


@dataclass(frozen=True, slots=True)
class TraceEdgeConversion:
    edges: tuple[TraceEdge, ...]
    accepted_count: int
    rejected_count: int
    rejection_reasons: tuple[str, ...]


def records_to_trace_edges(
    records: tuple[ProviderRawRecord, ...],
) -> TraceEdgeConversion:
    edges = []
    reasons = []
    seen = set()
    ordered = sorted(
        records,
        key=lambda item: (
            item.timestamp.isoformat() if item.timestamp else "",
            item.tx_hash,
            item.raw_reference or "",
        ),
    )
    for record in ordered:
        reason = _invalid_reason(record)
        if reason:
            reasons.append(reason)
            continue
        identity = record.raw_reference or (
            f"{record.tx_hash}:{record.from_address}:{record.to_address}:"
            f"{record.asset_symbol}:{record.amount_raw}"
        )
        if identity in seen:
            reasons.append("duplicate_record")
            continue
        seen.add(identity)
        amount = Decimal(record.amount_raw) / (
            Decimal(10) ** int(record.decimals or 0)
        )
        digest = sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
        evidence_id = (
            f"PROVIDER-{record.source_provider.upper()}-"
            f"{record.source_type.upper()}-{digest}"
        )
        edges.append(
            TraceEdge(
                edge_id=f"EDGE-{digest}",
                from_address=record.from_address or "",
                to_address=record.to_address or "",
                transaction_hash=record.tx_hash,
                asset=record.asset_symbol or "unknown",
                amount=amount,
                timestamp=record.timestamp,
                allocation_method=AllocationMethod.DIRECT_TRANSACTION,
                confidence=Decimal("1"),
                evidence_refs=(evidence_id,),
            )
        )
    return TraceEdgeConversion(
        edges=tuple(edges),
        accepted_count=len(edges),
        rejected_count=len(reasons),
        rejection_reasons=tuple(reasons),
    )


def _invalid_reason(record: ProviderRawRecord) -> str | None:
    if record.success is False:
        return "failed_transaction"
    if not record.tx_hash or not record.from_address or not record.to_address:
        return "missing_transaction_identity"
    if not record.asset_symbol:
        return "missing_asset"
    if record.timestamp is None or record.timestamp.tzinfo is None:
        return "missing_or_naive_timestamp"
    try:
        amount = Decimal(record.amount_raw or "")
    except InvalidOperation:
        return "invalid_amount"
    if amount <= 0:
        return "non_positive_amount"
    if record.chain is Chain.TRON:
        contract_type = str(record.metadata.get("contract_type", ""))
        if record.asset_symbol == "TRX" and contract_type != "TransferContract":
            return "invalid_native_trx_classification"
        if contract_type == "TransferAssetContract" and record.asset_symbol == "TRX":
            return "trc10_misclassified_as_trx"
    return None
