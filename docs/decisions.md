# Architecture Decisions

## ADR-077: PDF uses licensed system fonts without redistribution

PDF font resolution prefers an explicit path, then the environment override, then an
installed Windows CJK font. ChainSherlock does not copy or bundle proprietary Windows
fonts. Export status records only the safe font name and source category; no local
font path is persisted. ADR-033's partial policy remains the final fallback.

## ADR-074: Desktop execution defaults to explicit offline handlers

The Desktop composition root registers only approved CSV/XLS/XLSX handlers. It does
not auto-register Provider or AI execution. Provider-only plans therefore remain
unavailable until a later explicitly approved milestone.

## ADR-075: Offline handlers reuse public V2-V7 engines

Handlers orchestrate existing Importer, Normalizer, Analyzer, Investigation, Graph and
Report services. They contain no new analysis rules and write only execution-scoped
artifacts.

## ADR-076: Structured evidence suppresses Provider claims

When a case includes structured evidence, address analysis depends on its import step,
uses `case_evidence`, and has no Provider requirement. This prevents the UI and audit
from implying that a network Provider was used.

## ADR-068: Desktop navigation follows the investigation workflow

The primary navigation presents the next investigator action instead of internal
modules. A case moves through clues, goals, plan confirmation, execution, result
review and report review without requiring knowledge of internal classes.

## ADR-069: Case creation uses a wizard

The wizard separates case metadata, narrative context, evidence, clue confirmation
and goals. Addresses and transaction hashes are persisted only when the user checks
the explicit confirmation control.

## ADR-070: Primary UI uses human-readable labels

Goal and step codes are mapped at the UI boundary. Engineering model names and raw
JSON are excluded from primary views but remain available in persisted artifacts.

## ADR-071: Execution is represented as a timeline

Every step retains its explicit status, records, provider, warning and artifact
context. Unknown totals remain indeterminate and never receive a fake percentage.

## ADR-072: Result views preserve evidence categories

Confirmed facts, deterministic observations and candidate interpretations use
different labels and colors. Asset cards remain separated and do not sum currencies.

## ADR-073: Visual status always includes text

Color reinforces but never replaces status text. The palette uses green for
completed/confirmed, blue for running, amber for warning/candidate, red for failure,
and gray for cancelled/skipped/unavailable.

## ADR-063: PySide6 is the only desktop UI framework

The workbench uses PySide6 Essentials and Addons. No Electron, web server, Tkinter,
Streamlit or other UI runtime is introduced.

## ADR-064: UI contains no business logic

Views use UI adapters and existing Application Services. Provider, Analyzer, Graph
generation and AI internals remain outside the UI layer.

## ADR-065: Long operations use stage-based background workers

QRunnable and QThreadPool keep hashing, imports, planning, execution and exports off
the GUI thread. Unknown totals use indeterminate progress; no fake percentage is shown.

## ADR-066: Large tables use QAbstractTableModel

Case and investigation tables use model/view data access so large row collections are
not represented by thousands of QWidget instances.

## ADR-067: UI settings never persist secrets

Only `UISettings` fields are accepted. API keys, Authorization headers, passwords,
tokens, raw prompts and secret values are not valid persisted fields.

## ADR-060: Case output preserves epistemic boundaries

Confirmed facts may only originate from deterministic results or explicit reviewed
records. Rule-based observations remain observations; identity and service
inferences remain candidates with alternatives and limitations.

## ADR-061: Reports and packages are immutable versions

Every report uses a new `reports/vNNN` directory. Package manifests contain a
canonical SHA-256 inventory. Import validates all entries before committing a new
workspace and never overwrites an existing case.

## ADR-062: Deidentification is irreversible

Deidentified packages use salted deterministic aliases inside one export. Neither
the salt nor alias mapping is included, and original evidence is excluded.

## ADR-057: Execution Service is the single orchestration boundary

UI and CLI consumers must call CaseExecutionService rather than invoking handlers or
V2-V7 services directly.

## ADR-058: Step dispatch is registry-based

Each StepType is connected through a registered StepHandler adapter. The dispatcher does
not contain a large conditional over implementation modules.

## ADR-059: Failure policy preserves usable work

Fatal input/import failures stop execution. Recoverable and partial failures preserve
registered artifacts and permit later independent steps to continue.

## ADR-060: Cancellation is cooperative

CancellationToken is checked at handler boundaries and handlers receive cancellation
notification. Execution never kills a process or abandons an atomic temporary file.

## ADR-061: Resume and retry verify state

Resume requires the same plan version and valid artifact hashes, and skips completed
steps. Retry accepts only retryable failed, partial, or cancelled steps and is limited to
three attempts.

## ADR-062: Artifacts are immutable and case-relative

Only complete files inside the execution workspace can be registered. Each is addressed
relative to the case, hashed, sized, marked read-only, and verified before resume.

## ADR-063: Execution events have deterministic order

Events use monotonically increasing execution-local IDs and append-only JSON Lines.
Observer failures are isolated and safely logged.

## ADR-064: Detailed execution state stays outside CaseRecord

CaseRecord stores only execution summaries and active/latest IDs. Detailed steps, events,
logs, checkpoints, and artifacts remain in the execution workspace.

## ADR-051: Planner output is declarative and deterministic

The Planner creates stable, ordered PlanStep data from CaseRecord, InvestigationGoal, and
safe Settings. It cannot execute steps or create investigation findings.

## ADR-052: Provider planning uses public capability metadata

The Planner accepts only ProviderDescriptor values. It does not instantiate Providers,
inspect HTTP internals, test connections, or access credentials.

## ADR-053: Unsupported recommendations remain non-executable

Out-of-scope commercial intelligence actions use `unsupported_recommended_step`, are
disabled and skipped, and carry an explicit warning. They cannot enter executable steps.

## ADR-054: Explicit confirmation gates execution

Plans are non-executable until confirmed by a named user. Any modification increments the
plan version and clears prior confirmation.

## ADR-055: Unknown cost remains null

Without authoritative configured pricing, plan and step costs remain null. The Planner
emits a cost warning instead of inventing a numeric estimate.

## ADR-056: Case stores public planner JSON

CaseRecord persists goals and plans as forward-compatible public JSON. Planner models own
validation, which prevents the Case Layer from depending on Planner implementation code.

## ADR-046: Case workspaces use opaque identifiers

Case directories use generated `case_<32 lowercase hex>` IDs. Human-readable titles are
stored only as data and never become filesystem paths.

## ADR-047: Case persistence is atomic and forward-compatible

`case.json` is written through a same-directory temporary file and atomic replacement.
Schema migrations operate on copies, reject unsupported future schemas, and preserve
unknown fields through load/save cycles.

## ADR-048: Evidence is copied, immutable, and relatively addressed

Evidence is streamed into a case-owned file, hashed during import, marked read-only, and
stored using only a safe relative path plus its original basename. Source absolute paths
are not persisted.

## ADR-049: Audit history is append-only and hash-chained

Audit entries use append-only JSON Lines and link each entry to the previous SHA-256 hash.
The audit API has no edit/delete operation and redacts sensitive metadata before writing.

## ADR-050: Case deletion is recoverable

The repository delete service moves a complete case workspace under repository `.trash`
instead of permanently deleting it. UI confirmation remains deferred.

## ADR-037: Investigation consumes public results only

V6.5 accepts public AnalysisResult, GraphResult completeness metadata, and Local Labels. It does not inspect raw Provider, Importer, Normalizer, or HTTP internals.

## ADR-038: Deterministic and evidence-linked output

Stable ordering, settings snapshots, source-derived timestamps, structured warnings, reason codes, and evidence references make identical inputs produce identical results.

## ADR-039: Asset and direction scopes remain separate

Funding shares and distribution statistics are per asset. Direction reconciliation explicitly accounts for incoming, outgoing, self, neutral, unclassified, failed, and deduplicated records.

## ADR-040: Holding time is a declared approximation

Account-based chains use FIFO approximation with matched and unmatched amounts disclosed. Bitcoin is unsupported because account-based FIFO must not be presented as UTXO tracing.

## ADR-041: Labels are local and conservative

CSV, Excel, and JSON labels are normalized and matched locally. Rule-based categories are candidates, not identity or misconduct conclusions.

## ADR-042: No risk or criminal conclusions

Observations and Conclusion Facts report metrics and state changes only. V6.5 cannot output crime, fraud, money-laundering, suspect, or risk determinations.

## ADR-043: Partial boundaries cannot establish lifecycle stages

For partial Provider data, V6.5 suppresses startup, dormancy, and reactivation claims that could be artifacts of the fetched date boundary. Remaining stages, observations, and facts use low confidence and disclose instability.

## ADR-044: Rankings are asset-scoped amounts

Funding and outgoing report rankings are calculated independently per asset by amount. Transaction-count ranking remains available only as a legacy compatibility field and is not presented as the primary funding ranking.

## ADR-045: Investigation evidence joins the Report index

Investigation evidence IDs are represented in ReportDocument evidence and retain transaction hashes, addresses, calculation method, parameters, and the public source artifact.

## ADR-001: Explicit composition root

`Application` owns runtime registries and constructs a shared `Context`. This keeps wiring separate from domain code.

## ADR-002: Protocol-based extension points

Plugins and tools use Python Protocols so future implementations are structurally typed and do not require inheritance.

## ADR-003: Explicit plugin loading

Plugins are loaded only from module paths supplied by the caller. V1.1 performs no package scanning or automatic discovery.

## ADR-004: Backward-compatible settings name

`Settings` is the canonical configuration model. `AppConfig` remains an alias so V1 imports continue to work.

## ADR-005: Framework-independent Domain Layer

Domain entities use standard-library dataclasses and do not depend on Pydantic, import formats, provider responses, graph libraries, or AI integrations. Boundary models validate external data; normalizers will be the only path into canonical domain entities.

## ADR-006: Data Pipeline terminology

The V2 ingestion architecture is named Data Pipeline rather than Import Engine because CSV files, APIs, and blockchain providers will share the same `Importer -> Normalizer -> Domain -> Analyzer` direction.

## ADR-007: Dependency freeze after V2

V2 records the validated Python version and fully resolved environment in `requirements.lock`. Beginning with V3, third-party dependencies are frozen by default. A new dependency requires a concrete implementation need, compatibility review, updated lock file, and a full clean-environment test.

## ADR-008: Strict batch validation

The V2 pipeline rejects the entire batch when any row fails validation. It does not export partial results, preventing unvalidated records from entering downstream workflows.

## ADR-009: Deterministic field mapping

Mapping accepts exact normalized aliases only. When multiple source columns match a canonical field, the pipeline reports all candidates and requires an explicit override instead of guessing.

## ADR-010: One canonical transaction

All Importers produce canonical raw records, and all Normalizers produce the same Domain Transaction. Future file, API, explorer, and blockchain sources must use this boundary instead of defining source-specific transaction entities.

## ADR-011: Domain-only analyzers

Every V3 Analyzer accepts an `AnalysisContext` containing only Domain Transactions and an optional target address. Analyzers cannot inspect CSV, Excel, DataFrames, Importers, Normalizers, or raw records.

## ADR-012: Analyzer creation through a Factory

The Analysis Engine requests all Analyzer implementations from `AnalyzerFactory`. Selection uses registry lookup rather than analyzer-specific conditional branches.

## ADR-013: Asset separation

Statistics, timeline buckets, and counterparty totals store amounts by asset. Amounts from different assets are never added together. Top asset selection uses transaction count, not incomparable cross-asset value.

## ADR-014: Flow is data only

V3 Flow consists only of nodes and transaction edges. Rendering, graph libraries, HTML, Mermaid, GraphML, and visualization are deferred.

## ADR-015: Providers never construct Domain Transactions

Providers emit `ProviderRawRecord`; the Provider importer feeds existing V2 validation and normalization before Domain construction.

## ADR-016: Fallback is capability-scoped

A fallback is attempted only for a failed capability. Successful results from other capabilities are retained.

## ADR-017: Bitcoin preserves input/output identity

Bitcoin inputs and outputs remain separate raw records with index, address, and value metadata instead of being forced into an account model.

## ADR-018: Partial failures are explicit

Completeness, warnings, missing-data categories, and safe errors distinguish partial investigations from complete results.

## ADR-019: Deduplication is source-aware

Normal, token, internal, and Bitcoin input/output records use distinct stable identity keys; transaction hash alone is insufficient.

## ADR-020: Partial fallback requires missing capability data

A partial result triggers fallback only when `missing_data` identifies an incomplete capability. Truncation with usable data is sufficient and does not consume a fallback.

## ADR-021: Unconfirmed Bitcoin timestamps remain null

The Pipeline accepts a null timestamp only for Bitcoin records explicitly marked `confirmed = false`. No epoch or current-time value is fabricated.

## ADR-022: Record limits are hard per capability

Pagination slices an oversized response to the remaining capacity, stops immediately, and records truncation metadata. Providers cannot exceed the configured capability limit.

## ADR-023: Provider rejection is record-level

Provider batches may retain valid records and export rejected records with reasons and raw references. File-based V2 ingestion remains strict batch validation.

## ADR-024: Graph Engine consumes V3 Flow Data

Graph construction accepts only the public V3 AnalysisResult and Flow models. It does not inspect Provider, Importer, Normalizer, HTTP, or raw transaction internals.

## ADR-025: Graph Domain and NetworkX are separate

Graph Domain models are standard-library dataclasses. NetworkX is isolated behind an adapter so exports do not become Domain dependencies.

## ADR-026: MultiDiGraph preserves asset scope

V5 uses `MultiDiGraph` because the same directed address pair may have separate ETH, token, or other asset edges. Amounts from different assets are never merged.

## ADR-027: Node identity includes chain

Node IDs use `chain:normalized-address`, preventing addresses from different networks from colliding in later independently approved work.

## ADR-028: Deterministic graph truncation

Nodes and edges are ranked by stable metrics and IDs. Maximum node and edge limits are hard, target nodes are retained, and metadata records excluded counts and reasons.

## ADR-029: HTML is an escaped offline artifact

PyVis assets are embedded inline. Labels and tooltips are escaped and bounded; raw Provider errors, credentials, and unbounded metadata are not rendered.

## ADR-030: Exporters share one ReportDocument

Composer consumes only public V3/V5 results and public artifacts. Every exporter receives the same immutable report model and cannot recalculate analysis.

## ADR-031: Conclusions are deterministic and conservative

Conclusion text depends only on completeness and recorded gaps. It cannot assert identity, crime, fraud, money laundering, or risk.

## ADR-032: Evidence uses citations and SHA-256 manifests

Evidence references are safe relative paths with SHA-256, size, and modification time. Secrets and `.env` are excluded.

## ADR-033: PDF CJK font and partial export

PDF uses an explicit font, `CHAINSHERLOCK_PDF_CJK_FONT`, or an installed Windows CJK
font; no font is bundled. A PDF failure is isolated, successful files remain, and
status becomes partial.

## ADR-034: Assets and paths remain separated

Asset amounts are never summed across symbols. Output traversal is rejected, while absolute paths and credentials are redacted before presentation.

## ADR-035: Provider reports compose from public analysis JSON

The graph compatibility object remains limited to Graph construction. Report composition reads the complete public `analysis.json` artifact so Summary, Statistics, Counterparty and Timeline fields are not lost or recalculated.

## ADR-036: Report typography and wide tables

DOCX body Chinese uses 標楷體 and Latin text uses Times New Roman. Table Chinese uses 標楷體 and Latin, numbers, addresses and hashes use Consolas. PDF applies the configured CJK font and uses locally available Times New Roman／Consolas for Latin text, with portable built-in fallbacks. Tables wider than five fields render as deterministic field/value records in DOCX and PDF to remain readable on A4 pages.
# V7 Decisions

- AI 不直接讀 raw transactions；所有內容均源自可驗證的 V6.5 structured facts。
- AI 預設 disabled，外部呼叫必須由 `--ai` 明確啟用。
- Structured output 是必要條件；自由文字不得直接進入報告。
- Factual claims 必須有 Evidence；數字必須精確存在於輸入。
- Candidate、low-confidence 與 partial-data 語意不得提升為確定或完整。
- FIFO 僅是近似配對，不代表實際同一筆資金。
- Hallucination、解析或 provider 失敗一律使用 deterministic fallback。
- Privacy 預設 standard；off 仍遮罩 secrets，strict 另雜湊地址並移除 tx hashes。
- Human Review 預設 not_reviewed；AI 不取代人工判斷。
- Cache key 不包含 API key；寫入必須 atomic 且容許 corruption recovery。
- 無明確價格設定時 estimated cost 為 null，不猜測成本。

## V7.1 Decisions

- Offline Report 只使用公開 artifact；缺失資料以 unavailable 表示，不合成 AnalysisResult。
- Tagged V7 JSON 保持相容；loader 可額外接受完整的 untagged public NarrativeInput。
- Compact prompt 採欄位投影而非刪除核心 facts，並持續揭露 omitted counts。
- Mock/fallback 的 generated_at 由分析期間決定，確保相同輸入的完整輸出可重現。
- 真實模型驗收必須人工明確觸發；無 API Key 時直接停止且不發出請求。
