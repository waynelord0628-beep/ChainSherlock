# Development Progress

## V8 First-Hop final report tuning

- Unified every report address reference against one immutable Address Registry snapshot;
  report generation now fails safely instead of emitting `地址-未編號`.
- Consolidated the front-matter address reference into one core-address section while
  retaining the complete registry in CSV and technical artifacts.
- Separated primary and secondary roles/assets, generated dynamic Top-N headings, and
  stated the net-flow calculation denominator explicitly.
- Replaced text-based bars with deterministic first-hop flow, monthly USDT flow, and
  leading-destination charts.
- Strengthened the deterministic conclusion without implying transaction-level tracing,
  identity attribution, or confirmed off-ramps.
- Provider calls: 0. AI calls: 0.

## V8 第一層報告可讀性封版

- 明確區分 USDT 總紀錄、非零資金移轉與零值合約互動。
- 核心地址表縮減為五欄，主要角色、資產與金額改採分行顯示。
- 技術性排除改為 USDT 零值、非核心資產、微額原生資產及未分類事件分項揭露。
- 新增第一層資金流向、月度流入／流出及前五大去向三張規則式圖表。
- 補強地址功能判讀，並維持第一層分析與候選語意邊界。

## V8 Desktop Visual Final Validation

- 修正 System Readiness 語意：Blockscout「程式支援」與 Blockstream「公開服務」
  使用冷藍 supported 狀態，並明示未驗證／未測試連線，不再等同成功綠色。
- Empty State 的標題、說明與兩個操作按鈕改為同一置中視覺群組。
- 英文輔助標籤提升至 11px 與較高對比，但維持低於中文主標題的層級。
- LIVE EXECUTION 長案件／step 文字限制可視高度，完整內容保留於 tooltip；
  未知總量仍不顯示百分比，取消仍走 cooperative cancellation。
- UI targeted：266 passed；完整驗收：1,213 passed、1 skipped；`pip check` 通過。
- Windows 系統 DPI 未實際切換；20 項情境由既有 fixture/regression 覆蓋，
  但未宣稱完成全部人工逐頁操作。
- 未開始 V9 或 Windows 打包。

## V8 Pre-Packaging Crypto Investigation Command Center Redesign

- Desktop 改為深石墨藍黑的 blockchain forensics command center 視覺語言。
- 首頁完成 Crypto Investigation Hero、2×2／4-column operational cards、
  Investigation Queue empty/error/list states 與十項 System Readiness。
- 案件工作區改為 14 階段 navigation，加入 Case Intelligence 摘要、鏈／資產、
  Evidence integrity、Result、Investigation、Graph、Report 與 Audit 語意。
- LIVE EXECUTION 顯示人類可讀 stage、provider/capability、records、elapsed、
  artifact count；未知總量維持 indeterminate，不顯示假百分比。
- 新增 55 個 command-center UI regression cases；UI targeted 260 passed。
- 完整驗收：1,207 passed、1 skipped；`pip check` 通過。
- 本輪未新增分析功能、第三方 UI 套件或外部資產，未開始 V9／Windows 打包。

## V8 Milestone 8

- 完成 Provider-only address/transaction StepHandler 與 Desktop hybrid registry。
- 完成 Provider AnalysisResult 公開 JSON round-trip，Graph／Investigation 不重複
  發出網路請求。
- 完成 provider status、errors、rejected records 的 redaction、相對路徑、
  SHA-256 immutable artifact registration。
- 完成 fallback、partial preservation、單次 request workflow 與 secret regression。
- M8-A 受影響測試 356 passed；完整驗收 1,150 passed、1 skipped。
- M8-B 三鏈 bounded 真實驗收完成：Ethereum Blockscout fallback、TronGrid、
  Blockstream 均產出 Analysis、Graph 與 Investigation；0 fatal failure。
- 未使用 AI、商業 API、Cross-chain、Risk/AML；未開始 V9。

## V8.7.1

- PDF exporter 支援 Windows 系統標楷體自動偵測，環境變數仍可明確覆寫。
- `export_status.json` 記錄安全的 font name/source，不記錄字型絕對路徑。
- 找不到或無法載入 CJK 字型時，維持既有 partial export policy。
- Report／Case Output／M7 integration targeted tests：97 passed。
- 完整驗收：1,148 passed、1 skipped；`pip check` 無相依性錯誤。

## V8 Milestone 7

- 完成 CSV／XLS／XLSX Evidence 的離線 StepHandler registry 與 UI composition。
- 完成 Evidence integrity gate、Data Pipeline、Domain Transaction 與 Analysis 接線。
- 完成 deterministic Investigation、離線 Graph、Evidence Manifest 與四格式
  Case Report 接線。
- 完成 Planner `case_evidence` 資料來源與 import prerequisite，避免誤示
  Provider 已被呼叫。
- 完成 CSV、Excel、PDF partial policy、相對路徑與 Evidence tamper 回歸測試。
- 完整驗收：1,147 passed、1 skipped；`pip check` 無相依性錯誤。
- 未呼叫公開 Provider、真實 AI、付費模型或商業 API；未開始 V9。

## V8 Milestone 6

- 完成 workflow-oriented Home、最近案件、pending review 與 system status。
- 完成五步驟 Case Wizard、線索明確確認、Evidence 與 Goals 選擇。
- 完成左側 workflow navigation、next-action 提示與鍵盤操作。
- 完成 human-readable Plan cards、Execution timeline 與 global execution panel。
- 完成 Result Dashboard、Investigation、Counterparty、Graph、Narrative、Report、
  Audit 與 Settings cards。
- 完成低飽和青綠 Visual System、actionable empty states 與 99 項 M6 tests。

## V8 Milestone 5

- 完成本機 PySide6 Desktop Case Workbench 與 12 個案件工作區頁籤。
- 完成案件建立、搜尋、封存、可復原刪除、Evidence 匯入與 SHA-256 顯示。
- 完成 Planner、Execution 狀態、Case Result、Graph、Narrative、Report、Audit 串接。
- 完成 QRunnable/QThreadPool worker、cooperative cancellation 與安全錯誤顯示。
- 完成安全設定、AI disabled default、100 項 UI 測試及 TRON Mock Flow 驗收。

## V8 Milestone 4

- 完成 Case Artifact Aggregation 與公開 `CaseResult`。
- 完成 deterministic narrative，嚴格分離事實、觀察與候選解釋。
- 完成四格式案件報告、證據索引、稽核摘要與版本保留。
- 完成 full、report_only、deidentified 套件匯出、驗證與安全匯入。
- 完成公開 Application Service API、CLI 與 92 項 Milestone 4 測試。

## V8 Milestone 3

Status: completed.

- Added CaseExecution, StepExecution, ExecutionArtifact, ExecutionCheckpoint, result,
  warning, failure, event, and cooperative CancellationToken models.
- Added registry-based StepDispatcher and explicit StepHandler contract.
- Added atomic execution/step/checkpoint/manifest persistence and append-only event/log
  streams.
- Added immutable artifact registration with relative paths, SHA-256, size, completeness,
  safe metadata, and integrity verification.
- Added fatal, recoverable, partial, unsupported, cancelled, and manual-review policies.
- Added plan gating, cooperative cancellation, resume, bounded retry, Case summary, and
  append-only Audit integration.
- Added 90 focused Execution Service tests and Mock acceptance flows.
- Did not add PySide6, Desktop UI, Case Report composition, Narrative UI, packaging,
  commercial APIs, cross-chain, V9, or V2-V7 refactoring.

## V8 Milestone 2

Status: completed.

- Added InvestigationGoal with all approved goal types, priorities, targets, date ranges,
  completion criteria, state, creator, and user-confirmation fields.
- Added InvestigationPlan, PlanStep, ProviderRequirement, PlanWarning, and PlanConfirmation.
- Added deterministic address, transaction, structured-file, victim-payment,
  multi-address, local-label, investigation, graph, evidence-manifest, narrative, and
  report planning rules.
- Added dependency, order, target, capability, AI confirmation, unsupported-step, and
  pagination validation.
- Added explicit Provider, Capability, Cost, and unsupported-scope warnings using public
  metadata only.
- Added plan persistence and append-only audit events for plan creation, modification,
  and confirmation.
- Added 61 focused Milestone 2 tests.
- Did not add Execution Service, Provider execution, Case Report, Narrative integration,
  PySide6, Desktop UI, packaging, commercial APIs, cross-chain, V9, or V2-V7 refactoring.

## V8 Milestone 1

Status: completed.

- Added public CaseRecord, EvidenceRecord, CaseStatus, and CaseAuditEntry persistence models.
- Added safe opaque case IDs and workspace-confined path resolution.
- Added atomic repository create, load, save, list, archive, recoverable delete, and duplicate services.
- Added immutable evidence import with SHA-256, size, media type, relative path, and timezone-aware import time.
- Added append-only, redacted, SHA-256 hash-chained audit records.
- Added migration from legacy unversioned case JSON and preservation of unknown fields.
- Added 36 focused regression tests.
- Did not add Planner, Execution, Case Report, Narrative integration, PySide6, desktop UI,
  packaging, V9, or V2-V7 refactoring.

## Current version

V6.5 Investigation Feature Engine 已完成。

## V6.5 completion summary

- 建立只讀取公開 AnalysisResult／GraphResult／Provider 完整度／Local Label 的 deterministic feature layer。
- 完成供款、初始供款、階段、休眠恢復、活動、集中度、規則角色、Local Label、FIFO 近似、轉帳模式、關係、方向 reconciliation、Observations 與 Conclusion Facts。
- InvestigationResult 支援精確 JSON round-trip、evidence、observations、facts 與 label matches 輸出。
- Report 新增 Investigation section；Graph 支援 stage 與 funding 色彩。
- 新增五個 investigation／label CLI。
- V6.5 專屬測試 143 項；全專案 459 項通過。
- 已以公開 TronGrid 對指定 TRON 地址完成受限真實流程。

未加入 AI、LLM、Risk/AML Score、Cross-chain、商業情資 API 或 Web UI。

## V6.5 quality validation

- 使用 `TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE` 完成 TronGrid A/B 真實資料驗收。
- 測試 A：address transactions 50、token transfers 50；100 筆進入分析、85 筆具完整 flow endpoints；資料期間 2026-07-16 至 2026-08-04。
- 測試 B：address transactions 2,000、token transfers 500；2,500 筆進入分析、1,635 筆具完整 flow endpoints；資料期間 2026-01-01 至 2026-08-04。
- 兩組均維持 partial；A 為 max_records 截斷，B 仍有更多 address records，不將 Provider records 宣稱為地址完整交易總數。
- 修正方向對帳、資產金額排行、partial stage／dormancy 信心、dust TRX、Evidence traceability、Facts 一致性及 Report 橫向摘要表。
- 10 個 Conclusion Facts 已由 regression tests 重新計算一致。

## V4 completion summary

V4 Blockchain Provider Engine is implemented.

- Provider contracts, capabilities, structured errors, Registry, Factory, and fallback selection.
- async HTTP client with bounded retry, backoff, rate limiting, and timeouts.
- Etherscan, Blockscout, TronGrid, and Blockstream adapters.
- pagination limits, partial retention, source-aware deduplication, and TTL file-cache primitives.
- Provider Raw Records routed through the existing V2 Pipeline and V3 Analysis Engine.
- Provider CLI commands, safe output metadata, tests, and offline benchmark.

V4 adds no graph rendering, reports, AI, Agents, Risk/AML scoring, cross-chain, bridge, wallet, or OSINT functionality.

## V4.2 completion summary

- Missing capability data now triggers capability-scoped fallback and preserves primary errors.
- Provider status and error outputs record fallback resolution and final completeness.
- Shared pagination enforces hard per-capability `max_records` limits.
- Unconfirmed Bitcoin transactions retain null timestamps and remain available to non-timeline analyzers.
- Provider batches retain valid records and emit structured `rejected_records.json`.
- Real API validation covers Etherscan failure fallback, Blockscout, TronGrid, and Blockstream.

## V5 completion summary

- Added framework-independent GraphNode, GraphEdge, GraphMetadata, GraphResult, warning, and filter models.
- Added GraphBuilder, registry-based GraphFactory, aggregation, filtering, deterministic truncation, and styling.
- Added NetworkX `MultiDiGraph` adapter.
- Added deterministic JSON round-trip, GraphML, and offline PyVis HTML exports.
- Added `graph-file` and `graph-address` without changing existing CLI commands.
- Added HTML/XML injection protection, tooltip and transaction-hash safety limits.
- Added example outputs and bounded 100／10,000／100,000 transaction benchmark.

## Historical current version

V3 — Analysis Engine.

## Completed

- V1 project foundation and CLI.
- Typed configuration and core data models.
- Ethereum, TRON, and Bitcoin identifier detection.
- Plugin Protocol, Registry, and explicit module Loader.
- Tool Protocol and Registry, with no tools registered.
- Core `Application`, `Context`, and `Settings` composition layer.
- Reserved `shared` and `constants` packages.
- Domain entities for addresses, transactions, assets, counterparties, and cases.
- Shared chain, direction, and transaction-type enums owned by the Domain Layer.
- V2 dependency environment frozen in `requirements.lock` with Python 3.12.13.
- CSV, XLS, and XLSX Importers.
- deterministic column Mapping with explicit ambiguity candidates and overrides.
- validation for empty values, timestamps, amounts, addresses, duplicates, and formula injection.
- Ethereum, TRON, and Bitcoin Normalizers selected through a Factory.
- reusable `Raw -> Import -> Validate -> Normalize -> Domain -> Export` pipeline.
- `transactions_normalized.csv` and `summary.json` exports.
- `analyze-file` CLI with six column override options.
- Domain-only Analyzer Protocol and Analyzer Factory.
- Summary and Statistics Analyzers.
- Counterparty aggregation with asset-separated amounts.
- daily/monthly Timeline and hourly/weekday distributions.
- Flow node and edge data without graph rendering.
- complete AnalysisResult with metadata and warnings.
- JSON/CSV analysis exports and four analysis CLI commands.
- repeatable small, medium, and large benchmark fixtures.

## Validation

- Editable installation succeeds in a clean Python 3.12 virtual environment.
- All automated tests pass.
- CLI help command runs successfully.

## V8 Desktop manual validation follow-up

- Completed an isolated TRON case workflow through case creation, deterministic
  planning, plan approval, execution cancellation, results, investigation,
  graph empty state, deterministic narrative, four-format report generation,
  review, and audit verification.
- Corrected raw status/enumeration labels, workspace badge sizing, horizontal
  stage navigation, fallback narrative contrast, report-format badges, and
  review status wording.
- The provider step was cancelled cooperatively because TronGrid was not
  configured; no paid AI request was made.
- Actual Windows 100%/125%/150% system-DPI switching remains unverified.

## Scope guard

V2 contains no Provider, Graph, Timeline, Counterparty analysis, Report, AI, Risk, Cross-chain, Bridge, or on-chain API implementation.
V3 contains no Provider, blockchain API, graph rendering, report, Word/PDF, AI, Agent, Risk, Cross-chain, Bridge, or OSINT implementation.

## V6 — Report Engine

- 完成框架獨立 Report models、registry-based factory 與 deterministic composer。
- 完成 Evidence／Citation、SHA-256 manifest 與 `ReportDocument` JSON round-trip。
- 完成 Markdown、離線 HTML、DOCX、PDF exporter 與 partial failure 狀態。
- 完成 `report-file`、`report-address`、`report-tx`。
- 新增 80 項 V6 測試；完整測試為 305 passed。
- 完成 100／10,000／100,000 筆 Report benchmark 與 example outputs。
- V6 未加入 AI、Risk、Cross-chain、UI 或任何新分析邏輯。

## V6 完整驗收

- 以 `TR5WMAhpM9JkpouAT49X9pNHP8NPQkcGAE` 完成 TronGrid → V2 → V3 → V5 → V6 真實流程。
- 修正 Provider 報告未使用完整公開 `analysis.json` 的問題，TRX／USDT 摘要與精度均已保留。
- Markdown、離線 HTML、DOCX、PDF、Evidence manifest、JSON round-trip 與 partial export 均已實測。
- DOCX 已用 Microsoft Word 實際開啟與列印渲染；PDF 已逐頁渲染檢查。
- DOCX、PDF 與 HTML 列印樣式均套用：正文中文標楷體、英文與數字 Times New Roman；表格中文標楷體、英文與數字 Consolas。
- 寬表格改用可跨頁的欄位／值版面，避免 A4 裁切。

## V8 封版阻擋性資料品質修正

- 完成共用 Full History／Custom Date Range／Quick Preview `AnalysisScope`。
- 完成 Ethereum、TRON、Bitcoin 統一 pagination contract 與 required capability policy。
- Scope 已由 Wizard、Planner、Execution 傳至 Provider，範圍外資料在下游前排除。
- deterministic report 已分離資料母體、Partial 語意、Graph／Provider truncation、
  重要資產、Candidate 角色及 Evidence artifact mapping。
- AI report 改為完整 deterministic `ReportDocument` 的增補層。
- 離線完整驗收：`1306 passed, 1 skipped`；`pip check` 無破損相依性。
- 真實三鏈與單次 AI 驗收尚待最後階段；未開始 V9 或 Windows 打包。

### Final real validation

- Ethereum Full History and Custom Date Range completed through Blockscout fallback;
  required normal/token capabilities reached explicit end and all four reports exported.
- TRON Full History and Custom Date Range remained partial after TronGrid 429; reports
  preserved and used partial/specified-period language. Baseline differences are
  attributable to incomplete pagination, not silently accepted.
- Bitcoin Full/Custom attempts received persistent Blockstream 429 and were correctly
  failed with both required capabilities unavailable. A real-data regression also
  fixed target-relative Bitcoin output filtering and non-paginated UTXO completeness.
- One real `gpt-5-mini` call used 17,941 input and 1,800 output tokens. HTTP succeeded
  but output ended by length; Quality Gates retained all 32 deterministic sections,
  added zero AI sections, and exported all four fallback formats. No retry was made.
- Final post-fix validation: `1312 passed, 1 skipped`; `pip check` reports no
  broken requirements. The skip remains the opt-in real-AI integration test.
# V7

- 已完成 AI Provider abstraction、OpenAI-compatible HTTP provider、Mock 與 deterministic fallback。
- 已完成 bounded NarrativeInput、deterministic compaction、privacy modes 與 prompt injection 防護。
- 已完成 structured parser、claim/citation/numeric/hallucination validation。
- 已完成 NarrativeResult round-trip、7 項 artifacts、AI status/usage/prompt manifest。
- 已完成 `narrate-file`、`narrate-address`、`narrate-investigation` 與可選 Report AI 章節。
- 已新增 141 項 V7 規則測試；AI 預設關閉，不執行真實外部 API 測試。

## V7.1

- 三種公開 artifact 均可在離線狀態重建 Narrative/Report。
- Compact prompt benchmark 降低 55.35%，保留 16 facts、2 observations、42 evidence。
- Mock semantic output 10/10 完全一致；真實模型測試無 Key 時預設 skip。
- 新增 `validate-ai` 人工驗收指令、品質 checklist 與 fallback/mock 四格式 benchmark。
- V7/V7.1 regression tests 共 149 passed，另 1 項 real-AI integration test skipped。

## V7.3 bounded AI report output

- Compact input 改為每資產 Top 5、transitions/stages Top 10、observations 20、
  facts 30、limitations 15、Evidence IDs 50，並逐集合記錄 omitted count。
- Structured output 加入 section、paragraph、claim 與 refs 的硬性上限。
- Completion policy 依內容估算，minimum 3,000、default 3,500、hard max 8,000。
- `length`、截斷 JSON、schema、grounding 或必要章節失敗均不採用 AI 半成品；
  不自動進行第二次呼叫，完整 deterministic report 保留。
- Targeted：258 passed, 1 skipped；完整離線：1344 passed, 1 skipped；
  `pip check` 無損壞相依。
- V9 與 Windows 打包未開始。

### Live tuning result

- 共 6 次真實 `gpt-5-mini` 呼叫；成功後停止，未使用額外 9 次機會。
- 累計 input 56,316、output 18,464、total 74,780 tokens。
- Baseline：16,744 input／5,000 output，`length` fallback。
- 成功配置：10,105 input／2,727 output，finish `stop`；schema、grounding、
  Narrative validation 與 Report Quality Gates 全部通過。
- 相較 baseline：input 減少 39.6%，actual output 減少 45.5%，total 減少 41.0%。
- 最終報告保留 fixture 既有 26 deterministic sections、13 tables、
  Provider/completeness/Evidence Index，新增 12 AI sections；四格式 complete。
- Fixture 是舊版 partial artifact，實際基礎章節為 26，不宣稱不存在的 32 sections。

## V8 正式報告封版修正

- 完成 6,935 筆 TRON Full History scope-aware 報告；完整度為 complete。
- 四格式共用正式呈現模型：UTC+8、中文欄名、數字格式、表格拆分及章節順序一致。
- 建立 Address Registry，主文保留 Address ID，技術附錄保存完整可複製地址。
- 低重要性及 Spam Candidate 採可追溯、可恢復的候選排除，不修改原始 Evidence。
- 最終 PDF 共 27 頁，已逐頁渲染檢查封面、表頭、分頁、溢位、頁尾與 AI 章節。
- 驗收：targeted 191 passed；完整 pytest 1,383 passed、1 skipped；pip check 通過。

## V8 First-Hop Investigation Report Productization

- 建立 Goal 驅動的通用 `first_hop_product`，不依賴 Benchmark 地址、外部參考報告或 AI。
- 資產角色、來源／去向集中度、淨流量、第一層候選、時序、保守階段與案件特定後續任務
  均由 structured facts 產生。
- Provider 正式分析流程保存 `first_hop_product.json` 與本地 SVG 圖表 manifest；
  每張圖表保存 SHA-256。
- Local Label 增加 verification status 與 imported_at，衝突依可信層級處理。
- 以十類 recorded fixtures 覆蓋不同資產、完整度、Label、dust、期間與小資料集。
- 本階段不執行第二層追蹤、不呼叫 AI，亦不開始 Windows 打包。
# V8 正式報告全域版型與字體封版

- 將核心地址對照表與完整地址索引移至資產分析之前，後段不再重複完整 Registry。
- PDF、DOCX、HTML 共用 mixed-script formatter：中文使用標楷體，正文英文與數字使用 Times New Roman，表格英文與技術識別值使用 Consolas。
- PDF 頁尾使用「第 X 頁，共 Y 頁」；DOCX 使用 PAGE／NUMPAGES 欄位。
- 一般地址剖繪報告預設不執行或輸出地址污染、fake phishing、dusting 或相似地址章節；只有明確專用 Goal 且存在候選資料時才輸出未確認候選。
- Provider 與 AI 呼叫均為 0。

## V8 第一層幣流報告最終產品化

- 建立獨立的 First-Hop 產品化呈現模型，不修改原始 Analysis、Provider 或交易資料。
- 主文聚焦 USDT 主要價值資產與 TRX 營運資產；TRC10、Spam、dust 與未知資產下沉至可逆技術 artifact。
- 地址索引精簡為六欄；主要金額統一顯示至小數點後兩位。
- 第一層主要去向改為前三名調查候選卡，清楚區分目前可確認事項、尚待查證事項與限制。
- 新增規則式調查洞察、non_material_assets.csv 與 technical_exclusions.json。
- 一般報告主文不顯示 None、null、NaN、raw enum 或工程 metadata。
- 本輪 Provider 與 AI 呼叫均為 0。
## V8 Multi-hop Provider Resume Validation

- Added capability-level cursor checkpoint state for bounded multi-hop collection.
- Resume starts from the saved provider cursor and preserves accepted edges.
- Completed capabilities can be skipped without fetching their first page again.
- Cursor passthrough covers TronGrid, Etherscan, Blockscout and Blockstream.
- Offline targeted validation: 32 passed using synthetic identifiers only.

## V8 Multi-hop Planner and Execution Integration

- `TRACE_FUNDS` is now an explicit confirmed plan step for trace-funds goals.
- Each target address receives its own chain-aware bounded trace step.
- Case Evidence execution produces trace result and graph artifacts using real
  transaction hashes from the imported evidence.
- Desktop provider execution supports cooperative cancellation and serializable
  provider cursor checkpoints for resume.
- Targeted validation: Planner 77 passed; Execution/Provider integration 101 passed.
- Desktop/Case Result targeted validation: 371 passed.
- Full regression: 1,554 passed, 1 skipped; `pip check` reports no broken requirements.
- No Provider or AI calls were made during this integration milestone.
- Depth-5 synthetic product scenario validates aggregation, dispersion, return flow,
  trusted Local Label VASP stopping and evidence-backed transaction hashes.
- The Case Wizard now exposes multi-hop fund tracing as an explicit opt-in goal.

## V8 Multi-hop Analyst Controls

- Case Wizard exposes trace depth (1-5), node budget, materiality, direction and
  analyst-defined stop addresses.
- Planner clamps trace controls to safe product bounds and preserves deterministic
  ordering for manual stops.
- Offline and Provider execution apply manual stops as reached trace conditions.
- Targeted validation: 195 passed.

## V8 Live Provider Resume Gate

- A bounded TronGrid validation fetched two capabilities and saved both cursors.
- Resume used the saved cursors, preserved 182 prior edges and added 180 new edges.
- Total validation result: 362 distinct edges, four provider pages, zero safe errors.
- Fixed an empty-frontier defect: an unspecified asset filter now discovers and then
  separates Provider-returned assets instead of completing with zero queries.
- Live artifacts remain local and are excluded from Git.

## V8 Multi-hop Fund Tracing（開發驗收）

- 已完成公開 Trace contracts、同資產 FIFO、雙向 1～5 層 traversal、
  cooperative cancellation 與 checkpoint/resume。
- 已完成回流、循環、集中、分散及重複受款／分潤候選規則。
- 已完成可信 Local Label 下車點候選與停止條件。
- 已完成 Provider Raw Record → Trace Edge 嚴格轉換；TRX 與 TRC10 不混用。
- 已完成獨立四格式報告與 Graph JSON／GraphML／離線 HTML。
- 已新增 `trace-address` CLI；安全上限或 Provider 不完整會標記 partial。
- 合成資料 targeted tests：12 passed；完整 regression：1541 passed, 1 skipped。
- TronGrid bounded smoke test 已成功：原生與 TRC20 端點均可取得資料。
- 三層受限驗收使用 5 個地址／10 個 Provider page，收集 122 條 USDT／TRX
  候選 Edge；引擎保留 12 條與 Seed 可連通的 Edge、12 個節點並辨識 1 個
  分散候選。因每 capability 僅取 1 頁且查詢預算到頂，結果正確標記 partial。
- 本次真實驗收未產生或提交案件 artifact，API Key 未寫入檔案或 Git。
