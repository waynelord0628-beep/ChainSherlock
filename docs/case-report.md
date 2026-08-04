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

## Professional deterministic and AI-assisted reports

The report now records scope, Provider completeness, pipeline populations,
material assets, funding/outgoing counterparties, stages, dormancy, holding time,
patterns, confirmed facts, deterministic findings, candidate interpretations,
unresolved questions, follow-up, limitations, conclusion, a deduplicated Evidence
Index and technical appendix.

Full History partial output uses “currently acquired data” language. Custom ranges
use “within the specified period”. Different assets are never summed. Configurable
per-asset materiality moves dust/spam candidates to the appendix.

AI enrichment is disabled by default and may only append grounded sections to the
same complete ReportDocument. Failed Quality Gates preserve every deterministic
section and table and record a safe fallback reason.
