from datetime import datetime

from crypto_investigator.investigation.investigation_result import InvestigationEvidenceRef


def build_evidence(edges, funding, created_at: datetime | None):
    evidence = [
        InvestigationEvidenceRef(
            evidence_id="IF0",
            feature="analysis_scope",
            source_type="analysis_flow",
            source_reference="AnalysisResult.flow",
            tx_hashes=tuple(sorted(edge.tx_hash for edge in edges)),
            addresses=tuple(
                sorted({edge.source for edge in edges} | {edge.target for edge in edges})
            ),
            calculation="deterministic feature calculation over public analysis flow",
            parameters={"edge_count": len(edges)},
            created_at=created_at,
        )
    ]
    by_source = {}
    for edge in edges:
        by_source.setdefault(edge.source.casefold(), []).append(edge)
    for source in funding.sources:
        records = by_source.get(source.address.casefold(), ())
        evidence.append(
            InvestigationEvidenceRef(
                evidence_id=f"IF{len(evidence)}",
                feature="funding_source",
                source_type="analysis_flow",
                source_reference="AnalysisResult.flow",
                tx_hashes=tuple(sorted(edge.tx_hash for edge in records)),
                addresses=(source.address,),
                calculation="incoming transaction count / all incoming transactions",
                parameters={"rank": source.rank},
                created_at=created_at,
            )
        )
    return tuple(evidence)
