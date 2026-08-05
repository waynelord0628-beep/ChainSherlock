# Changelog

## Unreleased — First-Hop final report tuning

- Use a single Address Registry snapshot across report sections and exports.
- Remove duplicate visible core-address tables and clarify primary/secondary roles.
- Replace textual chart approximations with deterministic image charts in all four formats.
- Make Top-N labels reflect the actual row count.
- Clarify the net-flow denominator and strengthen the bounded deterministic conclusion.
- Remove obsolete references directing readers to a later address table.

## V8 - First-hop report readability finalization

- Simplified the core address table and removed unsourced transaction-count cells.
- Reconciled 872 USDT records with 837 non-zero transfers and 35 zero-value interactions.
- Corrected technical exclusion summaries and added deterministic flow visualizations.
- Strengthened the rule-based conclusion without adding AI or Provider calls.

## V8 Desktop Visual Final Validation

- Corrected public-provider readiness badges so support is not presented as verified
  connectivity.
- Grouped Investigation Queue empty-state actions with its title and guidance.
- Improved helper-label readability and bounded long LIVE EXECUTION content.
- Added focused regressions for provider semantics, empty-state composition, helper
  typography and long execution text.

## V8 Pre-Packaging Crypto Investigation Command Center Redesign

- Replaced the light desktop presentation with a local-only blockchain-forensics theme.
- Added a static QPainter node-flow hero, operational case cards and investigation queue.
- Added textual readiness, chain, asset, integrity, provider and execution presentation.
- Expanded the case workspace to fourteen visible investigation stages without changing
  execution, provider, analysis, graph or report service boundaries.
- Added dark forensic presentations for Result, Investigation, Evidence, Graph, Report
  and Audit data and responsive DPI/viewport regressions.

## V8 Milestone 8

- Added hybrid offline/Provider analysis StepHandlers to Desktop Execution.
- Connected Etherscan/Blockscout, TronGrid and Blockstream results to Case artifacts.
- Added verified AnalysisResult deserialization for downstream Graph and Investigation.
- Added defense-in-depth Provider output redaction and safe execution metadata.
- Added recorded fallback/partial integration tests and a bounded real-provider validator.

## V8.7.1

- Added automatic Windows 標楷體 discovery for PDF export.
- Added safe PDF font name/source metadata without local path disclosure.
- Preserved explicit environment overrides and partial export on unavailable fonts.

## V8 Milestone 7

- Added the default offline Execution Registry to the Desktop composition root.
- Connected immutable CSV/XLS/XLSX evidence to existing Pipeline and Analysis engines.
- Connected deterministic Investigation, offline Graph, Evidence Manifest and Case Report.
- Made structured-evidence address plans depend on local imports without Provider claims.
- Added offline CSV/Excel end-to-end, partial PDF and evidence-integrity regressions.

## V8 Milestone 6

- Redesigned the desktop UI around the investigation workflow.
- Added a five-step case wizard and explicit clue confirmation.
- Replaced primary raw JSON views with human-readable cards, dashboards and timelines.
- Added left-stage navigation, next-action guidance and global execution status.
- Added a consistent visual system, actionable empty states and keyboard shortcuts.
- Added 99 M6 workflow tests and expanded the UI benchmark.

## V8 Milestone 5

- Added the PySide6 desktop case workbench and no-argument launcher.
- Added case list, creation, workspace tabs, evidence, planning and output actions.
- Added background workers, cancellable UI operations and safe status rendering.
- Added local Graph WebEngine boundary and allowlisted settings persistence.
- Added 100 UI tests, a bounded TRON mock acceptance flow and UI benchmark.

## V8 Milestone 4

- Added CaseResult aggregation from case, plan, execution, evidence and public artifacts.
- Added deterministic case narrative and versioned case reports.
- Added evidence index, audit summary, unresolved questions and follow-up recommendations.
- Added full, report-only and irreversible deidentified case packages.
- Added safe package validation/import and Case Output CLI commands.

## V8 Milestone 3

- Added Case Execution models, event system, context, registry, policies, and public API.
- Added registry-based Step Dispatcher and handler contract.
- Added atomic execution state, append-only events/logs, checkpoints, and artifact manifest.
- Added immutable SHA-256 artifact registration and resume integrity checks.
- Added partial/fatal handling, cooperative cancellation, manual suspension, resume, and
  retry with a three-attempt limit.
- Added Case summary and append-only audit integration.
- Added 90 focused tests and Mock success, partial, cancellation/resume, and fatal flows.

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

## V8 Desktop manual validation follow-up

- Localized workspace, plan, report, and review status labels.
- Replaced rotated workspace tabs with readable horizontal, scrollable tabs.
- Fixed deterministic fallback narrative contrast in the dark theme.
- Limited report status badges to the four user-facing report formats.
- Added regression coverage for the corrected desktop presentation states.

- 新增 grounded AI Investigation Narrative Engine。
- 新增 deterministic fallback、privacy/redaction、cache 與 usage contract。
- 報告新增經驗證且標記為「AI 輔助敘事」的可選章節。
- 新增三個 `narrate-*` CLI 指令與 V7 benchmark。

## V7.1

- 修正 `narrate-investigation --report` 的 AnalysisResult 依賴。
- 支援從 investigation、narrative input 或 narrative artifact 離線重建。
- 新增 compact prompt、尺寸比較、10-run consistency 與人工 real-AI validation。
- 補齊 deterministic/mock Report composition 及四格式效能量測。

## V8 pre-release data quality

- Added shared Analysis Scope, Time Scope Result and cross-chain pagination metadata.
- Added Ethereum/TRON/Bitcoin capability completeness policies.
- Fixed Full History caps, Custom Date Range propagation and downstream filtering.
- Separated Provider, normalized, Analysis, Investigation and Graph populations.
- Professionalized deterministic reports, Partial language, asset materiality,
  neutral Candidate roles and deduplicated Evidence references.
- Changed AI reporting from replacement to validated enrichment of the complete
  deterministic ReportDocument.
- Fixed fallback-resolved required capability errors incorrectly forcing partial.
- Added date-bound pagination stopping for newest/oldest ordered custom scopes.
- Fixed Blockstream address analysis to exclude unrelated incoming transaction outputs
  and to preserve target-relative outgoing/change semantics.
- Added complete pagination metadata for non-paginated Bitcoin transaction/UTXO calls.
- Compacted engineering collections in human-facing tables while retaining full JSON.
- Fixed a cold-start circular import between Provider service and Application exports.

## V7.3 bounded AI output

## V8 正式鑑識報告呈現

- 正式主表移除工程欄位，統一中文欄名、百分比、金額、停留時間與 UTC+8 顯示。
- 加入 Address Registry、artifact-level Evidence Index 與低重要性／Spam Candidate 附錄。
- PDF 與 DOCX 支援重複表頭、禁止列跨頁、標題接續內容及獨立封面。
- 修正正式 Full History 不沿用 preview 上限，並保存 pagination checkpoint 與 scope metadata。
- AI 專業綜合改為 deterministic report enrichment，且位於 Evidence Index 前。

## V8 First-Hop Report Productization

- Added a chain-agnostic, Goal-driven first-hop investigation product service.
- Added deterministic executive summaries, asset roles, concentration, time series,
  cautious stage detection, trace-candidate priorities and case-specific follow-up tasks.
- Added offline SVG chart artifacts with SHA-256 manifests.
- Extended Local Label provenance and verification metadata.
- Suppressed empty and duplicate report sections while preserving four-format parity.

- Bounded compact facts, output paragraphs, claims and grounding references.
- Replaced the legacy 1,800/2,000-token assumption with a live-validated
  3,000–8,000 completion policy and 3,500 default.
- Added explicit truncation/fallback metadata without storing prompts, request
  bodies, credentials or local absolute paths.
- Added Report UI metadata for provider/model, token counts, finish reason,
  validation and fallback.
- Reduced repeated Evidence address payloads and enabled minimal GPT-5 reasoning.
- Added dynamic grounding enums and deterministic citation reconstruction.
- Fixed long decimal tails being misclassified as Bitcoin addresses.
- Added explicit partial migration for legacy artifacts with saved periods.
# Unreleased

- 修正正式報告地址索引位置、全域中英數混排字體、PDF／DOCX 頁碼及 HTML 字體語意 class。
- 新增安全字型 fallback metadata，不保存本機字型路徑或字型檔。
- 地址污染、dusting 與相似地址分析改為專用 Goal 明確啟用，普通 First-Hop 報告不再產生空白或誤導章節。

## First-Hop report productization

- Reworked the deterministic first-hop presentation into a reader-focused case report.
- Limited principal asset facts to USDT and operational TRX for the current product scope.
- Moved unknown, TRC10, spam and low-materiality records into reversible technical artifacts.
- Added top-three first-hop investigation cards and evidence-bound deterministic insights.
- Removed raw missing values, engineering enums and internal metadata from the main report.
