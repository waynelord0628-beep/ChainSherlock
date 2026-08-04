# Case Report

`CaseResultService` aggregates a case without rerunning Providers or analysis.
`CaseReportService` creates a deterministic narrative and reuses the V6 exporters
for Markdown, offline HTML, DOCX and PDF.

Each run writes to a new `reports/vNNN` directory and retains previous versions.
The report includes confirmed facts, deterministic observations, candidate
interpretations, unresolved questions, recommended follow-up, limitations,
completeness, evidence index, audit summary and review status.

Confirmed facts never come from AI narrative text. Candidate identities and service
classifications remain explicitly labelled as candidates. PDF failure follows the
existing partial-export policy and does not remove successful formats.
