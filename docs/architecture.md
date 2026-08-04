# ChainSherlock Architecture

## V8 Milestone 4: Case Output

```text
Case + Plan + Executions + registered artifacts
                        |
                        v
              CaseArtifactAggregator
                        |
                        v
                    CaseResult
                 /       |       \
        deterministic  Report   Package
          narrative    versions export/import
```

Case Output 只讀取公開案件紀錄與已登錄 artifacts。`CaseResult` 分開保存
confirmed facts、deterministic observations 與 candidate interpretations。
報告重用 V6 `ReportDocument` 與 exporters，每次輸出建立新的 `reports/vNNN`。
套件使用 allowlist、相對路徑與 SHA-256 manifest，匯入驗證完成後才建立新的
安全 case ID。

## V8 Milestone 3: Case Execution Service

```text
confirmed InvestigationPlan
          |
          v
 CaseExecutionService -- plan gate / policy / state transitions
          |
          v
 StepDispatcher --> registered StepHandler adapters --> V2-V7 public services
          |
          +--> deterministic events.jsonl
          +--> immutable hashed artifacts
          +--> atomic execution/step/checkpoint state
          +--> append-only Case Audit
```

Execution state is stored under
`cases/<case_id>/executions/<execution_id>/`, with separate step, artifact, log, and
checkpoint directories. `execution.json`, step state, checkpoints, manifests, and
CaseRecord summaries use atomic replacement. Events, structured logs, and Case Audit are
append-only.

The dispatcher is registry-based. Execution code does not branch across V2-V7 internals;
handlers adapt public services to a uniform contract. Unregistered, unsupported,
unconfirmed, invalid-version, or archived-case plans fail the execution gate.

Failures are classified as fatal, recoverable, partial, unsupported, or cancelled.
Fatal input/import failures stop later steps. Recoverable and partial failures preserve
artifacts and allow later independent steps. Cancellation is cooperative and checked at
handler boundaries; no process is forcibly terminated.

Resume verifies the current plan version and all retained artifact hashes, skips completed
steps, and resumes only handler-supported work. Retry is limited to three attempts,
requires a retryable failed/partial/cancelled step, and preserves prior artifacts.

## V8 Milestone 2: Investigation Planner

```text
CaseRecord + InvestigationGoal + safe Settings snapshot
                         |
                         v
             DeterministicPlanner
                         |
          public ProviderDescriptor metadata
                         |
                         v
 InvestigationPlan -> validation -> user confirmation
        |                                  |
        +--> CaseRecord.plans              +--> executable_steps boundary
        +--> append-only Case Audit
```

The Planner creates declarative steps only. It never calls a Provider, reads Provider
internals, runs analysis, or manufactures investigation facts and evidence. Provider
selection and warnings consume only public `ProviderDescriptor` capability metadata.

Stable plan and step identifiers are derived from canonical inputs. Validation checks
unique IDs and ordering, dependency existence and cycles, disabled prerequisites,
report/narrative prerequisites, target/chain requirements, pagination bounds, and
unsupported steps. Unknown costs remain `null` and produce an explicit warning.

An unconfirmed plan is not executable. Confirmation records the actor, timezone-aware
time, enabled steps, and a secret-free Settings snapshot. Planner state is persisted as
public JSON in CaseRecord and plan creation, modification, and confirmation append Case
Audit entries.

## V8 Milestone 1: Case Foundation

```text
CaseRepository
    |
    +--> safe opaque case_id --> CaseWorkspace
    |                              |
    |                              +--> case.json (atomic replace)
    |                              +--> evidence/ (immutable copies)
    |                              +--> audit/audit.jsonl (append-only hash chain)
    |
    +--> schema migration --> CaseRecord (unknown fields preserved)
```

The Case Layer is a local persistence boundary. Workspace directory names use generated
`case_<32 lowercase hex>` identifiers and never derive from a case title. All persisted
evidence references are relative to the workspace. Repository JSON writes use a temporary
file, flush and `fsync`, followed by atomic replacement.

Evidence import streams the source into a workspace-owned copy while calculating SHA-256
and byte size. Records also retain the media type, source basename, and timezone-aware
import time; the source absolute path is never persisted. Imported copies are marked
read-only and can be verified against their recorded digest.

Audit entries are appended as JSON Lines and linked using SHA-256 hashes. The public API
does not expose update or removal operations for audit entries. Sensitive metadata is
redacted before persistence.

This milestone does not depend on Planner, Execution, Report, Narrative, Provider,
Analyzer, Graph, AI, PySide6, or desktop UI modules.

## V6.5 Investigation Feature Layer

```text
public AnalysisResult ----+
public GraphResult -------+--> InvestigationFeatureEngine
Provider completeness ----+            |
Local Label Registry -----+            v
                                  InvestigationResult
                               / evidence / JSON / report
```

此層不讀取 Importer、Normalizer、Provider raw response 或 HTTP 內部物件。規則、排序、時間窗、方向 reconciliation、evidence ID 與輸出均為 deterministic。不同資產不加總；不完整來源會降低可信度並產生 warning，不補猜資料。

Local Label 僅支援 CSV、XLS/XLSX、JSON，不連接商業情資 API。Account-based chain 的停留時間使用明示的 FIFO approximation；Bitcoin 不套用該近似政策。Conclusion Facts 只描述可驗證事實，不輸出身分、犯罪、詐欺、洗錢或風險結論。

## Project tree

```text
src/crypto_investigator/
├── cli.py
├── analyzers/
│   ├── base.py
│   ├── counterparty.py
│   ├── engine.py
│   ├── export.py
│   ├── factory.py
│   ├── flow.py
│   ├── models.py
│   ├── statistics.py
│   ├── summary.py
│   └── timeline.py
├── core/
│   ├── application.py
│   ├── context.py
│   ├── export.py
│   ├── pipeline.py
│   └── settings.py
├── domain/
│   ├── address.py
│   ├── asset.py
│   ├── case.py
│   ├── counterparty.py
│   ├── metadata.py
│   └── transaction.py
├── importers/
│   ├── base.py
│   ├── csv_importer.py
│   ├── excel_importer.py
│   ├── factory.py
│   ├── mapping.py
│   └── validator.py
├── normalizers/
│   ├── base.py
│   ├── bitcoin.py
│   ├── ethereum.py
│   ├── factory.py
│   └── tron.py
├── models/
├── plugins/
├── tools/
└── utils/
```

## Module dependency

```text
CLI
 └── Core DataPipeline
      ├── Importer Factory -> CSV/Excel Importers -> Mapping
      ├── Validator
      ├── Normalizer Factory -> Chain Normalizers
      ├── Domain Transaction
      └── Transaction Exporter
```

Dependencies point inward toward `domain`. Domain modules do not import Importer, Provider, Analyzer, Graph, Report, Pydantic, or pandas code.

## Data flow

```text
Raw CSV/XLS/XLSX
        |
        v
Importer + Mapping
        |
        v
Canonical raw records
        |
        v
Validation (entire batch)
        |
        v
Normalizer Factory
        |
        v
Domain Transaction
        |
        v
transactions_normalized.csv + summary.json
```

Invalid or ambiguous data stops before Domain conversion and export. No source is permitted to bypass this flow.

## Completed interfaces

- `Importer` Protocol and file-based Importer Factory.
- deterministic Mapping Engine with explicit ambiguity reporting.
- batch Validator and structured validation issues.
- `Normalizer` Protocol, base implementation, and chain factory.
- canonical framework-independent Domain Transaction and Metadata.
- reusable `DataPipeline.to_domain()` and `DataPipeline.run()`.
- normalized CSV and JSON summary export.
- Plugin and Tool extension registries from V1.1.

## Future interfaces

The following are interfaces for later approved versions, not V2 implementations:

- API and blockchain importers that emit the same canonical raw records.
- provider adapters that enter through the Data Pipeline.
- analyzers that accept only Domain entities.
- graph, timeline, counterparty, risk, AI, bridge, and cross-chain modules.

No future interface may bypass validation, normalization, or Domain conversion.

## Analysis layer

The Analysis Layer depends on Domain Transactions and standard-library data structures. It does not import pandas, Importers, Normalizers, Providers, graph libraries, report generators, or AI clients.

The `AnalysisContext` contains an immutable transaction tuple and an optional target address. The target allows direction and counterparty relationships to be evaluated without mutating Domain Transactions.

## Analysis dependency diagram

```text
CLI
 ├── V2 DataPipeline -> Domain Transactions
 └── V3 AnalysisEngine
      ├── AnalyzerFactory
      │    ├── SummaryAnalyzer
      │    ├── StatisticsAnalyzer
      │    ├── CounterpartyAnalyzer
      │    ├── TimelineAnalyzer
      │    └── FlowAnalyzer
      ├── AnalysisResult
      └── AnalysisExporter -> JSON/CSV data
```

## Analyzer flow

```text
Domain Transactions
        |
        v
AnalysisContext
        |
        v
AnalyzerFactory
        |
        +--> Summary
        +--> Statistics
        +--> Counterparties
        +--> Timeline
        +--> Flow data
        |
        v
AnalysisResult
        |
        v
analysis.json / summary.json / counterparties.csv
timeline.json / timeline.csv / flow.json
```

Amounts are never combined across assets. Flow output is structured data and contains no rendered graph representation.

## V4 Provider Layer

```text
Blockchain API -> Provider -> ProviderRawRecord
ProviderRawRecord -> V2 Validation -> V2 Normalization -> Domain Transaction
Domain Transaction -> V3 Analysis Engine -> data outputs
```

The Provider Layer owns HTTP, retries, rate limiting, pagination, cache primitives, response parsing, capabilities, and safe errors. Domain has no Provider or HTTP dependency, and Analysis accepts only Domain Transactions.

Selection follows configured primary, capability check, request, then capability-scoped fallback. Successful capability results survive later failures. Status output records completeness, warnings, missing-data categories, and safe errors.

Cache keys contain provider, chain, capability, normalized identifier, safe query parameters, and page/cursor; API keys are excluded. Pagination is bounded by `max_pages`, `max_records`, and `page_size`, and repeated cursors stop collection.

## V4.2 reliability flow

A partial primary result triggers fallback only when it declares missing capability data. A partial but sufficient result, such as an intentional record limit, does not trigger fallback. Primary and fallback records are merged and source-aware deduplication runs after collection.

Provider pagination applies `max_records` per capability. An oversized page is sliced before records enter the Pipeline, no extra page is requested, and status records truncation details.

Unconfirmed Bitcoin records may retain `timestamp = null` only when source metadata explicitly says `confirmed = false`. Timeline excludes them; Summary, Statistics, Counterparty, and Flow retain them. Provider batch validation is record-level and writes rejected records, while file-based V2 batches remain strict and atomic.

## V5 Graph Layer

```text
V3 AnalysisResult.flow
        |
        v
GraphBuilder -> GraphResult -> GraphFilter
        |                         |
        v                         v
NetworkX Adapter          deterministic limits
        |
        +--> flow_graph.json
        +--> flow.graphml
        +--> flow.html
```

Graph Domain models are standard-library dataclasses and do not depend on NetworkX or PyVis. The NetworkX adapter is an export boundary and produces `MultiDiGraph` so asset-scoped parallel edges remain distinct.

Node identity is `chain + normalized address`. Edge identity is `source + target + direction + asset scope`. Amounts are always stored by asset and never combined across currencies.

Filtering and truncation are deterministic. Target nodes are retained, graph limits are applied before rendering, and excluded counts plus truncation reasons are recorded in metadata. Partial Analysis completeness, missing data, safe Provider error summaries, and rejected record counts propagate into Graph metadata.

HTML rendering uses inline assets, bounded tooltips, escaped labels, and no Provider credentials. GraphML converts datetimes to ISO 8601 and complex values to JSON strings while preserving Decimal text.

## V6 Report Layer

```text
AnalysisResult + GraphResult + public status/error artifacts
                         |
                         v
                  ReportComposer
                         |
                         v
                  ReportDocument
             /       |       |       \
       Markdown    HTML     DOCX      PDF
                         |
             export status / errors

local evidence -> SHA-256 manifest -> citations -> Evidence Index
```

Composer 是唯一的內容組裝邊界；Exporter 只呈現同一份 `ReportDocument`，不重新分析交易或建立圖。Report Layer 不依賴 Provider、Importer、Normalizer、HTTP、AI、Risk 或 Cross-chain internals。

輸出路徑限制在指定目錄，HTML 不可信內容強制 escape，秘密與絕對路徑在進入文件前遮罩。PDF 字體是明確的環境設定邊界；缺少 CJK 字體只使 PDF 失敗，其他格式保留並回報 partial。
# V7 AI Narrative Boundary

V7 的唯一 AI 輸入是由 V6.5 `InvestigationResult` 建立的 bounded `NarrativeInput`。
資料依序通過 deterministic compaction、privacy/redaction、分區 Prompt、structured
response parser、claim/citation/numeric/hallucination validation，再成為
`NarrativeResult`。任何失敗均轉入 deterministic fallback，既有 Report exporter
仍負責 HTML/DOCX/PDF escaping。

AI Provider 位於獨立 protocol boundary，Narrative Engine 不依賴鏈上 Provider、raw
transaction 或商業風險服務。Prompt 將所有標籤、地址、metadata 與 notes 放在
`UNTRUSTED_DATA_JSON` 邊界；cache key 不含 API key。Privacy mode 在 provider boundary
前執行。AI 與 deterministic facts 在 Report 中分章呈現，且 Human Review 預設為
`not_reviewed`。

## V7.1 Offline Reconstruction

公開 artifact loader 可識別 `InvestigationResult`、`NarrativeInput` 與
`NarrativeResult`。前兩者可重建或重新驗證 deterministic narrative；僅有
NarrativeResult 時，OfflineReportComposer 只輸出已保存章節，並將 target、chain、
period、evidence 等缺失值標記 `unavailable`。這條路徑不引用 Analysis internals，
也不具備 Provider 或原始檔入口。

Prompt compaction 分為 standard/compact；兩者使用相同排序與核心 fact contract。
Compact 僅投影必要欄位、限制 reason codes 與 hashes，不刪除 Conclusion Facts 或已選取
Observations。真實模型驗收位於明確的人工 CLI boundary，預設測試永不呼叫外部模型。
