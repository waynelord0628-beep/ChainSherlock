# Planned Work

## After V6.5

- V6.5 acceptance is complete. Do not start V7 without a new explicit prompt.
- Known limitations: no Bitcoin UTXO holding-time matching, cross-chain tracing, commercial label intelligence, or AI-generated narrative.
- Future dependency additions require explicit need, lock update, and clean-environment validation.
- Provider pagination remains bounded; expanded real-data validation may remain partial because of limits or rate limiting.
- Candidate roles without Local Label remain unconfirmed candidates.
- FIFO approximation is not provenance tracing and cannot identify the actual onward movement of a specific incoming transfer.
- Pattern details beyond the current public summary remain limited; no new feature family was introduced during quality validation.

## V5 completed scope

- Graph Domain Model and GraphBuilder from V3 Flow Data.
- Graph filtering, aggregation, labels, styling, and deterministic safety limits.
- NetworkX adapter plus JSON, GraphML, and offline HTML exports.
- File and Provider address Graph CLI workflows.
- Security tests, example outputs, benchmark, and documentation.

## Deferred beyond V5

- Markdown／Word／PDF reports, AI／LLM／Agents, Risk／AML scoring, cross-chain correlation, bridge matching, OSINT, Web UI, and wallet operations.

## V4.2 completed scope

- Capability-scoped fallback for incomplete partial results.
- Hard pagination record limits.
- Unconfirmed Bitcoin null timestamp handling.
- Provider record-level rejection and partial analysis output.
- Provider status/error consistency and redaction verification.

## V4 completed scope

- Ethereum, TRON, and Bitcoin Provider adapters.
- Provider contracts, Registry, Factory, capability selection, and fallback.
- HTTP resilience, bounded pagination, cache primitives, partial outputs, and deduplication.
- Provider-to-Pipeline-to-Analysis integration and CLI.

## Deferred beyond V4

- Graph rendering, reports, AI, Agents, Risk/AML scoring, cross-chain and bridge correlation, OSINT, and wallet operations.

## V2 completed scope

- CSV Importer.
- XLS and XLSX Importers.
- batch Validator.
- Transaction Normalizer.
- Canonical Domain Transaction output.
- normalized CSV and JSON summary Export.

Implemented flow: `Raw Data -> Importer -> Validation -> Normalizer -> Domain Transaction -> Export`.

## Explicitly deferred

- Excel import.
- Blockchain providers and API integrations.
- Counterparty analysis, timeline, and graph analysis.
- Reports, caching, graphs, labels, and heuristics.
- Concrete plugins and tools.

## V3 completed scope

- Summary and Statistics Analyzers.
- Counterparty aggregation with asset separation.
- daily/monthly Timeline and hourly/weekday distribution.
- data-only Flow nodes and edges.
- Analyzer Factory and complete AnalysisResult.
- JSON/CSV analysis exports and analysis CLI commands.

## Deferred beyond V3

- blockchain Providers and APIs.
- graph rendering and graph libraries.
- Markdown, Word, PDF, or other reports.
- AI, Agent, Risk, OSINT, Bridge, and Cross-chain features.

Future work must be approved and delivered one milestone at a time.
## After V6

- V6 acceptance is complete. Do not begin V7 without an explicit prompt.
- Keep the locally configured CJK font requirement documented; no font files are bundled.
