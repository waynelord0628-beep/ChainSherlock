# Changelog

## Unreleased — V5

- Added Graph Domain models, Builder, Factory, aggregation, filtering, styling, and safety limits.
- Added NetworkX `MultiDiGraph` conversion.
- Added deterministic Graph JSON, GraphML, and offline PyVis HTML.
- Added `graph-file` and `graph-address` commands while preserving existing CLI behavior.
- Added Graph security tests, example outputs, and a bounded 100,000-transaction benchmark.
- Added only the approved `networkx`, `pyvis`, and `jinja2` dependencies.

## Unreleased — V4.2

- Fixed partial Provider results so missing capability data triggers fallback.
- Added fallback resolution and structured error details to Provider outputs.
- Enforced hard per-capability record limits across shared pagination.
- Added explicit null timestamp handling for unconfirmed Bitcoin transactions.
- Added Provider record-level rejection and `rejected_records.json`.
- Validated Etherscan failure fallback, Blockscout, TronGrid, and Blockstream against live APIs.

## Unreleased — V4

- Added Etherscan, Blockscout, TronGrid, and Blockstream Provider adapters.
- Added async HTTP reliability, bounded pagination, cache primitives, fallback, partial failures, and source-aware deduplication.
- Routed Provider records through the existing V2 Pipeline and V3 Analysis Engine.
- Added Provider CLI commands, safe outputs, tests, and an offline benchmark.

## Unreleased — V3

- Added the Domain-only Analysis Engine and Analyzer Factory.
- Added Summary, Statistics, Counterparty, Timeline, and data-only Flow Analyzers.
- Added AnalysisResult, structured analysis models, and target-relative directions.
- Added asset-separated statistics and counterparty amount aggregation.
- Added `analysis.json`, `summary.json`, `counterparties.csv`, `timeline.json`, `timeline.csv`, and `flow.json`.
- Added four analysis CLI commands.
- Added small, medium, and large fixtures plus a repeatable benchmark baseline.
- Added no third-party dependencies.

## Unreleased — V2

- Added a reproducible dependency freeze with the validated Python and package versions.
- Established a V3 policy against adding third-party dependencies without demonstrated need.
- Added CSV, XLS, and XLSX Importers.
- Added deterministic field Mapping and explicit column overrides.
- Added batch Validation, including duplicate and spreadsheet formula injection detection.
- Added Ethereum, TRON, and Bitcoin Normalizers and a Normalizer Factory.
- Added the reusable Data Pipeline and canonical Domain Transaction conversion.
- Added normalized CSV and JSON summary exports.
- Added the `analyze-file` CLI command.

## 0.1.2 — V1.2

- Added a framework-independent Domain Layer.
- Added domain entities for address, transaction, asset, counterparty, and case.
- Moved shared blockchain enums into the Domain Layer while preserving model imports.
- Defined the minimal V2 Data Pipeline scope without implementing it.

## 0.1.1 — V1.1

- Added architecture documentation.
- Added Plugin Protocol, Registry, and Loader.
- Added Tool Protocol and Registry.
- Added core Application, Context, and Settings layers.
- Added shared and constants namespaces.
- Added no business functionality.

## 0.1.0 — V1

- Added project foundation, configuration, data models, identifier detection, and CLI.
## V6

- Added ReportDocument composition, evidence citations and JSON round-trip.
- Added Markdown, offline HTML, DOCX and configurable-CJK PDF exports.
- Added partial export status/error artifacts and three report CLI workflows.
- Added V6 examples, security coverage and report benchmarks.
