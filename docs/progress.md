# Development Progress

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
