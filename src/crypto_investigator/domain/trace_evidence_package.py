"""Deterministic technical exports for multi-hop trace validation."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

from crypto_investigator.domain.fund_tracing import TraceResult
from crypto_investigator.domain.investigation_priority import InvestigationPriority
from crypto_investigator.domain.trace_accounting import (
    BranchConservation,
    PathAllocation,
)


@dataclass(frozen=True, slots=True)
class TraceAuditRecord:
    audit_id: str
    event_type: str
    subject_id: str
    decision: str
    reason: str
    evidence_refs: tuple[str, ...] = ()


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_value(item) for item in value]
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    return value


def write_trace_evidence_package(
    output_dir: Path,
    *,
    result: TraceResult,
    allocations: Iterable[PathAllocation] = (),
    conservation: Iterable[BranchConservation] = (),
    priorities: Iterable[InvestigationPriority] = (),
    audit_records: Iterable[TraceAuditRecord] = (),
) -> dict[str, Path]:
    """Write auditable CSV/JSON artifacts without secrets or absolute paths."""

    root = output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    allocation_items = tuple(allocations)
    conservation_items = tuple(conservation)
    priority_items = tuple(priorities)
    audit_items = tuple(audit_records)

    outputs = {
        "all_paths": root / "all_paths.csv",
        "service_candidates": root / "service_candidates.csv",
        "terminal_candidates": root / "terminal_candidates.csv",
        "provider_incomplete": root / "provider_incomplete.csv",
        "allocation_groups": root / "allocation_groups.csv",
        "trace_graph": root / "trace_graph.json",
        "trace_audit": root / "trace_audit.json",
    }
    _csv(
        outputs["all_paths"],
        (
            "edge_id",
            "from_address",
            "to_address",
            "tx_hash",
            "asset",
            "amount",
            "timestamp",
            "allocation_method",
            "confidence",
            "evidence_refs",
        ),
        (
            (
                edge.edge_id,
                edge.from_address,
                edge.to_address,
                edge.transaction_hash,
                edge.asset,
                str(edge.amount),
                edge.timestamp.isoformat(),
                edge.allocation_method.value,
                str(edge.confidence),
                "|".join(edge.evidence_refs),
            )
            for edge in result.edges
        ),
    )
    _csv(
        outputs["service_candidates"],
        (
            "candidate_id",
            "address",
            "asset",
            "priority_tier",
            "priority_score",
            "priority_reasons",
            "required_next_action",
            "limitations",
        ),
        (
            (
                item.candidate_id,
                item.address,
                item.asset,
                item.tier.value,
                str(item.score),
                "|".join(item.priority_reasons),
                item.required_next_action,
                "|".join(item.limitations),
            )
            for item in priority_items
        ),
    )
    _csv(
        outputs["terminal_candidates"],
        (
            "address",
            "label",
            "label_source",
            "asset",
            "received_amount",
            "transaction_count",
            "confidence",
            "category",
            "evidence_refs",
        ),
        (
            (
                item.address,
                item.label or "",
                item.label_source or "",
                item.asset,
                str(item.received_amount),
                str(item.transaction_count),
                str(item.confidence),
                item.category or "",
                "|".join(item.evidence_refs),
            )
            for item in result.off_ramp_candidates
        ),
    )
    incomplete = [
        (
            item.condition.value,
            item.reason,
            "|".join(item.evidence_refs),
        )
        for item in result.stop_conditions
        if item.condition.value == "provider_incomplete"
    ]
    _csv(
        outputs["provider_incomplete"],
        ("condition", "reason", "evidence_refs"),
        incomplete,
    )
    _csv(
        outputs["allocation_groups"],
        (
            "path_id",
            "allocation_type",
            "amount_status",
            "exclusive_amount",
            "shared_cap",
            "shared_group_id",
            "bottleneck_upper_bound",
            "accounting_eligible",
            "confidence",
            "evidence_refs",
            "limitation",
        ),
        (
            (
                item.path_id,
                item.allocation_type.value,
                item.amount_status.value,
                _optional_decimal(item.exclusive_amount),
                _optional_decimal(item.shared_cap),
                item.shared_group_id or "",
                _optional_decimal(item.bottleneck_upper_bound),
                str(item.accounting_eligible).lower(),
                str(item.confidence),
                "|".join(item.evidence_refs),
                item.limitation or "",
            )
            for item in allocation_items
        ),
    )
    graph_payload = {
        "schema_version": 1,
        "run_id": result.run_id,
        "seed": result.seed.to_dict(),
        "scope": result.scope.to_dict(),
        "nodes": [item.to_dict() for item in result.nodes],
        "edges": [item.to_dict() for item in result.edges],
        "conservation": [item.to_dict() for item in conservation_items],
    }
    outputs["trace_graph"].write_text(
        json.dumps(graph_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    audit_payload = {
        "schema_version": 1,
        "run_id": result.run_id,
        "records": [_value(asdict(item)) for item in audit_items],
    }
    outputs["trace_audit"].write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return outputs


def _optional_decimal(value: Decimal | None) -> str:
    return "" if value is None else str(value)


def _csv(path: Path, headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
