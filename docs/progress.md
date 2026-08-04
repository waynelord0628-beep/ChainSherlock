# Development Progress

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

## Current version

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
