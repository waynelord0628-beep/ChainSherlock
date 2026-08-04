# Architecture Decisions

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

PDF requires `CHAINSHERLOCK_PDF_CJK_FONT`; no font is bundled. A PDF failure is isolated, successful files remain, and status becomes partial.

## ADR-034: Assets and paths remain separated

Asset amounts are never summed across symbols. Output traversal is rejected, while absolute paths and credentials are redacted before presentation.

## ADR-035: Provider reports compose from public analysis JSON

The graph compatibility object remains limited to Graph construction. Report composition reads the complete public `analysis.json` artifact so Summary, Statistics, Counterparty and Timeline fields are not lost or recalculated.

## ADR-036: Report typography and wide tables

DOCX body Chinese uses 標楷體 and Latin text uses Times New Roman. Table Chinese uses 標楷體 and Latin, numbers, addresses and hashes use Consolas. PDF applies the configured CJK font and uses locally available Times New Roman／Consolas for Latin text, with portable built-in fallbacks. Tables wider than five fields render as deterministic field/value records in DOCX and PDF to remain readable on A4 pages.
