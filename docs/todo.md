# Planned Work

## After V8 Milestone 7

- Await explicit approval before real Provider StepHandler integration.
- Real Provider desktop acceptance must remain bounded and must verify credential
  redaction, pagination, partial failure and deduplication.
- Windows packaging, installer, code signing and clean-machine acceptance remain later
  V8 work.
- Graph node synchronization and report approval signatures remain deferred.
- Do not begin V9 without explicit approval.

## After V8 Milestone 6

- Await explicit approval before any Windows packaging or V9 work.
- Provider credential connection tests remain mocked in automated UI tests.
- Graph node-click synchronization depends on future bridge support from the existing
  HTML artifact; M6 provides the safe selection boundary only.
- Report approval signatures and external reviewer identities remain deferred.

## After V8 Milestone 5

- Await explicit approval before Milestone 6.
- Windows packaging, installer, auto-update and code signing remain deferred.
- Real Provider execution remains a bounded manual action; M5 acceptance uses mock
  handlers and does not call paid AI or commercial APIs.
- Dedicated visual editors for every planner field and human report signatures remain
  follow-up work.

## After V8 Milestone 4

- Await explicit approval before starting the Desktop UI milestone.
- Human review workflow and report approval signatures remain deferred.
- Imported packages preserve public summaries and registered artifacts; they do not
  imply that an execution can be resumed.

## V8 Milestone 3 boundary

- Case Execution Service is complete.
- Concrete V2-V7 adapters are intentionally not auto-registered; approved handlers must
  be supplied explicitly by the application composition root.
- Cancellation is cooperative and cannot interrupt code that ignores CancellationToken.
- Execution persistence targets a single local process; cross-process file locking is not
  included.
- Debug case-run/resume/cancel CLI commands remain optional and were not added.
- Case Report integration, Narrative UI, PySide6, Desktop UI, Windows packaging, and
  Milestone 4 remain deferred pending explicit approval.

## V8 Milestone 2 boundary

- Investigation Planner is complete.
- Execution Service remains unavailable; confirmed plans only expose a validated list of
  executable declarative steps.
- No Provider request, analysis, report generation, narrative generation, UI, or packaging
  is performed by the Planner.
- AI planning is not implemented. The optional narrative step can only be proposed when
  explicitly enabled and always requires confirmation.
- Milestone 3 must not begin without explicit approval.

## V8 Milestone 1 boundary

- Case Foundation is complete.
- Investigation Planner, Execution Service, Case Report, Narrative integration, PySide6,
  Desktop UI, and Windows packaging remain deferred until explicit Milestone approval.
- Duplicate currently creates a new case record without copying evidence; evidence package
  duplication policy remains a later application-service decision.
- Repository operations are designed for a single local process; cross-process locking is
  not part of Milestone 1.

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
- Keep the CJK environment override and Windows system-font fallback documented; no
  proprietary font files are bundled.
# V7 Known Follow-ups

- 真實 AI integration test 僅在使用者明確同意且提供有效環境變數後執行。
- `narrate-investigation --report` 需要對應 AnalysisResult 才能重新組成完整 V6 報告。
- V7 不包含任何 V8、cross-chain、risk/AML 或商業 intelligence API 功能。

## V7.1 Remaining

- 真實 AI 的 3-run 驗收仍需使用者提供環境變數並人工執行 `validate-ai`。
- Narrative-only 離線報告無法還原 artifact 中未保存的 target、chain 或 Evidence Index；
  這些欄位會保持 unavailable。
