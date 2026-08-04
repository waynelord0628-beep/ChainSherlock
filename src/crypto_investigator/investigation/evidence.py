from datetime import datetime

from crypto_investigator.investigation.investigation_result import InvestigationEvidenceRef


def build_evidence(edges, funding, created_at: datetime | None):
    evidence = []
    by_source = {}
    for edge in edges:
        by_source.setdefault(edge.source.casefold(), []).append(edge)
    for source in funding.sources:
        records = by_source.get(source.address.casefold(), ())
        evidence.append(
            InvestigationEvidenceRef(
                evidence_id=f"IF{len(evidence) + 1}",
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
