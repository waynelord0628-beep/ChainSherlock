# Desktop Investigation Workflow

## Home

Home contains one primary action, recent cases, open/running/partial/review summary
cards and safe system-status text. It does not perform Provider calls.

## Case Wizard

The five steps separate metadata, case context, evidence, confirmed clues and goals.
Unconfirmed address or transaction text is discarded. Imported files continue through
the existing immutable Evidence service.

## Workflow navigation

The case header derives the next action from persisted public state:

- no goals → review clues and add goals;
- no plan → generate a deterministic plan;
- unconfirmed plan → review and confirm;
- no execution → start execution;
- completed or partial execution → review results and generate a report.

## Plan and Execution

Plan cards translate internal step codes into Traditional Chinese labels and expose
reason, provider, bounded parameters, warnings and confirmation. Execution uses a
stage timeline. Completed steps remain completed during resume.

## Results and Investigation

The dashboard presents scope, completeness, asset-separated summaries and important
observations. Investigation preserves the three epistemic categories: confirmed fact,
deterministic observation and candidate interpretation.

## Graph, Narrative and Report

Graph embeds only an existing local `flow.html`. Narrative clearly identifies
deterministic fallback and AI-disabled state. Report preview lists immutable versions,
formats, completeness and export status.

## Review and safety

Audit uses a human-readable timeline while technical metadata stays secondary.
Credentials are masked, UI settings are allowlisted, paths are reduced to safe file
names, and errors pass through existing redaction.
