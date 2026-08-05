"""Rule-based multi-hop flow findings over verified transaction edges."""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from decimal import Decimal

from crypto_investigator.domain.fund_tracing import (
    FlowPatternFinding,
    FlowPatternType,
    TraceEdge,
    TraceNode,
)


@dataclass(frozen=True, slots=True)
class FlowPatternSettings:
    min_aggregation_sources: int = 3
    min_dispersion_destinations: int = 3
    min_repeated_payments: int = 3
    min_shared_interactions: int = 2


def detect_flow_patterns(
    *,
    seed_address: str,
    nodes: tuple[TraceNode, ...],
    edges: tuple[TraceEdge, ...],
    settings: FlowPatternSettings = FlowPatternSettings(),
) -> tuple[FlowPatternFinding, ...]:
    """Return deterministic candidates; identity and intent remain unconfirmed."""

    findings: list[FlowPatternFinding] = []
    hop_by_tx = {node.transaction_hash: node.hop for node in nodes}
    by_asset = defaultdict(list)
    for edge in edges:
        by_asset[edge.asset].append(edge)

    for asset in sorted(by_asset):
        asset_edges = by_asset[asset]
        findings.extend(
            _degree_findings(asset, asset_edges, hop_by_tx, settings)
        )
        findings.extend(
            _return_and_cycle_findings(seed_address, asset, asset_edges, hop_by_tx)
        )
        findings.extend(
            _revenue_share_findings(asset, asset_edges, hop_by_tx, settings)
        )

    return tuple(
        replace(finding, finding_id=f"FLOW-{index:04d}")
        for index, finding in enumerate(findings, start=1)
    )


def _degree_findings(asset, edges, hop_by_tx, settings):
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for edge in edges:
        incoming[edge.to_address].append(edge)
        outgoing[edge.from_address].append(edge)
    findings = []
    for address, related in sorted(incoming.items()):
        sources = {edge.from_address for edge in related}
        if len(sources) >= settings.min_aggregation_sources:
            findings.append(
                _finding(
                    FlowPatternType.AGGREGATION,
                    asset,
                    related,
                    hop_by_tx,
                    (address, *sorted(sources)),
                    {
                        "source_count": str(len(sources)),
                        "transaction_count": str(len(related)),
                        "total_amount": str(sum((e.amount for e in related), Decimal("0"))),
                    },
                    ("multiple_material_sources", "funds_converge_on_one_address"),
                )
            )
    for address, related in sorted(outgoing.items()):
        destinations = {edge.to_address for edge in related}
        if len(destinations) >= settings.min_dispersion_destinations:
            findings.append(
                _finding(
                    FlowPatternType.DISPERSION,
                    asset,
                    related,
                    hop_by_tx,
                    (address, *sorted(destinations)),
                    {
                        "destination_count": str(len(destinations)),
                        "transaction_count": str(len(related)),
                        "total_amount": str(sum((e.amount for e in related), Decimal("0"))),
                    },
                    ("multiple_material_destinations", "funds_disperse_from_one_address"),
                )
            )
    return findings


def _return_and_cycle_findings(seed, asset, edges, hop_by_tx):
    findings = []
    returns = [edge for edge in edges if edge.to_address == seed and edge.from_address != seed]
    if returns:
        findings.append(
            _finding(
                FlowPatternType.RETURN_FLOW,
                asset,
                returns,
                hop_by_tx,
                (seed, *sorted({edge.from_address for edge in returns})),
                {
                    "transaction_count": str(len(returns)),
                    "total_amount": str(sum((e.amount for e in returns), Decimal("0"))),
                },
                ("returns_to_seed",),
            )
        )
    cyclic = [edge for edge in edges if _path_exists(edge.to_address, edge.from_address, edges, edge)]
    if cyclic:
        findings.append(
            _finding(
                FlowPatternType.CYCLIC_FLOW,
                asset,
                cyclic,
                hop_by_tx,
                tuple(sorted({a for edge in cyclic for a in (edge.from_address, edge.to_address)})),
                {"cycle_closing_edge_count": str(len(cyclic))},
                ("transaction_edges_form_cycle",),
            )
        )
    return findings


def _revenue_share_findings(asset, edges, hop_by_tx, settings):
    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge.from_address].append(edge)
    findings = []
    for sender, related in sorted(outgoing.items()):
        recipient_counts = Counter(edge.to_address for edge in related)
        repeated = {
            address: count
            for address, count in recipient_counts.items()
            if count >= settings.min_repeated_payments
        }
        if len(repeated) < 2:
            continue
        amounts = Counter(str(edge.amount) for edge in related if edge.to_address in repeated)
        findings.append(
            _finding(
                FlowPatternType.REVENUE_SHARE_CANDIDATE,
                asset,
                [edge for edge in related if edge.to_address in repeated],
                hop_by_tx,
                (sender, *sorted(repeated)),
                {
                    "repeated_recipient_count": str(len(repeated)),
                    "payment_count": str(sum(repeated.values())),
                    "repeated_amount_value_count": str(
                        sum(1 for count in amounts.values() if count > 1)
                    ),
                },
                ("multiple_repeated_recipients", "repeat_payment_pattern"),
            )
        )
    return findings


def _finding(pattern, asset, edges, hop_by_tx, addresses, metrics, reasons):
    evidence = tuple(dict.fromkeys(ref for edge in edges for ref in edge.evidence_refs))
    return FlowPatternFinding(
        finding_id="PENDING",
        pattern_type=pattern,
        asset=asset,
        hop=max((hop_by_tx.get(edge.transaction_hash, 0) for edge in edges), default=0),
        address_refs=tuple(addresses),
        metrics=metrics,
        reason_codes=tuple(reasons),
        confidence=Decimal("0.7"),
        evidence_refs=evidence,
        candidate_only=True,
        limitations=("Rule-based candidate; identity and intent require verification.",),
    )


def _path_exists(start, target, edges, excluded):
    adjacency = defaultdict(set)
    for edge in edges:
        if edge is not excluded:
            adjacency[edge.from_address].add(edge.to_address)
    pending = [start]
    visited = set()
    while pending:
        address = pending.pop()
        if address == target:
            return True
        if address in visited:
            continue
        visited.add(address)
        pending.extend(sorted(adjacency[address] - visited))
    return False
