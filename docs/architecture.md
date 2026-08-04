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
