from crypto_investigator.reports.models import ReportCitation, ReportEvidence


def build_citations(
    evidence: tuple[ReportEvidence, ...], section_id: str
) -> tuple[ReportCitation, ...]:
    return tuple(
        ReportCitation(
            citation_id=f"C{index}",
            evidence_id=item.evidence_id,
            display_text=f"[{item.evidence_id}]",
            source=item.source,
            source_reference=item.source_reference,
            section_id=section_id,
        )
        for index, item in enumerate(evidence, start=1)
    )
