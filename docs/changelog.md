# Changelog

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
