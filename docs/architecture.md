# ChainSherlock Architecture

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
