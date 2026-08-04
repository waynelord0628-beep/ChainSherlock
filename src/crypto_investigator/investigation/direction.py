from crypto_investigator.investigation.investigation_result import DirectionReconciliation


def reconcile_directions(analysis, target_address: str) -> DirectionReconciliation:
    edges = analysis.flow.edges
    target = target_address.casefold()
    incoming = outgoing = self_transfers = neutral = unclassified = 0
    for edge in edges:
        source = edge.source.casefold()
        destination = edge.target.casefold()
        if source == target and destination == target:
            self_transfers += 1
        elif destination == target:
            incoming += 1
        elif source == target:
            outgoing += 1
        elif source and destination:
            neutral += 1
        else:
            unclassified += 1
    metadata = getattr(analysis, "metadata", {}) or {}
    failed = int(metadata.get("failed_transaction_count", 0))
    duplicates = int(metadata.get("duplicate_removed_count", 0))
    total = len(edges)
    reconciled = total == incoming + outgoing + self_transfers + neutral + unclassified
    return DirectionReconciliation(
        total,
        incoming,
        outgoing,
        self_transfers,
        neutral,
        unclassified,
        failed,
        duplicates,
        reconciled,
    )
