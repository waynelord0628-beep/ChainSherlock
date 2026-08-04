# Changelog

## V8 Milestone 2

- Added deterministic Investigation Goal and Plan models.
- Added address, transaction, structured-evidence, victim-payment, comparison, local-label,
  graph, investigation, evidence-manifest, optional narrative, and report planning rules.
- Added plan/dependency validation, safe settings snapshots, and user-confirmation gating.
- Added public capability, provider credential, unknown cost, and unsupported-scope warnings.
- Added Case persistence and append-only audit integration for planner state.
- Added 61 focused tests without Provider execution or UI dependencies.

## V8 Milestone 1

- Added Case models, safe workspace IDs, and forward-compatible schema migration.
- Added atomic filesystem Case Repository services.
- Added immutable Evidence import and SHA-256 integrity verification.
- Added append-only, redacted, hash-chained Audit Log.
- Added 36 focused Case Foundation tests without UI dependencies.

## V6.5

- Added deterministic Investigation Feature Engine and public result models.
- Added funding, stage, dormancy, activity, concentration, distribution, pattern, relationship, observation, and conclusion-fact features.
- Added CSV/XLS/XLSX/JSON Local Label Registry and five investigation/label CLI commands.
- Added evidence-linked exports, exact JSON round-trip, Report section, and Graph stage/funding styling.
- Added 143 V6.5 tests, bounded benchmarks, and live TronGrid validation.
- Added no AI, LLM, Risk/AML scoring, cross-chain, commercial intelligence API, or Web UI.
- Validated limited and expanded TronGrid samples against the same address.
- Fixed public direction reconciliation to account for records without complete flow endpoints.
- Changed report funding and outgoing rankings to asset-scoped amount ordering.
- Prevented partial source boundaries from creating startup/dormancy claims and removed dust TRX from fixed-amount findings.
- Added evidence-linked observations and conclusion facts plus readable landscape report tables.

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
- Validated the complete TronGrid report flow with the requested TRON address.
- Fixed Provider report composition to retain complete public analysis data.
- Fixed Markdown table line breaks, DOCX/PDF page numbering, mixed-script fonts,
  and wide-table overflow.
- Hardened report text against event-handler, script, formula and traversal payloads.
# V7

- 新增 grounded AI Investigation Narrative Engine。
- 新增 deterministic fallback、privacy/redaction、cache 與 usage contract。
- 報告新增經驗證且標記為「AI 輔助敘事」的可選章節。
- 新增三個 `narrate-*` CLI 指令與 V7 benchmark。

## V7.1

- 修正 `narrate-investigation --report` 的 AnalysisResult 依賴。
- 支援從 investigation、narrative input 或 narrative artifact 離線重建。
- 新增 compact prompt、尺寸比較、10-run consistency 與人工 real-AI validation。
- 補齊 deterministic/mock Report composition 及四格式效能量測。
