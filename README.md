# ChainSherlock

ChainSherlock is a local-first blockchain transaction investigation toolkit.

**Current milestone:** V4 Blockchain Provider Engine
**Package version:** 0.1.2

## Installation

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

For the exact V2 validated environment:

```powershell
pip install -r requirements.lock
pip install -e .
```

## Quick start

```powershell
python -m crypto_investigator --help
python -m crypto_investigator detect 0x0000000000000000000000000000000000000000
python -m crypto_investigator analyze-file transactions.csv
python -m crypto_investigator providers
python -m crypto_investigator analyze-address <ADDRESS>
python -m crypto_investigator analyze-tx <TX_HASH> --chain ethereum
pytest
```

V2 adds a reusable Data Pipeline. It imports transaction files, validates every row, normalizes chain-specific representation into Domain Transactions, and exports normalized data. It does not perform transaction analysis.

V3 adds a Domain-only Analysis Engine. It does not connect to blockchain providers, draw graphs, generate reports, use AI, or perform cross-chain analysis.

V4 adds asynchronous Etherscan, Blockscout, TronGrid, and Blockstream Esplora adapters. Provider records always enter the existing V2 Pipeline before the existing V3 Analysis Engine. Configure secrets only through environment variables copied from `.env.example`.

## Blockchain Providers

- Ethereum: Etherscan primary, Blockscout fallback.
- TRON: TronGrid.
- Bitcoin: Blockstream Esplora.
- Capabilities, bounded pagination, retries, partial failures, source-aware deduplication, and file cache primitives are explicit contracts.
- Outputs add `provider_status.json`, `provider_errors.json`, and sanitized files under `raw/`.

## Data Pipeline

Every supported source follows one direction:

`Raw Data -> Importer -> Validation -> Normalizer -> Domain Transaction -> Export`

The pipeline rejects an invalid batch before Domain conversion or export. Importers never select chain-specific behavior; `NormalizerFactory` owns that decision.

## Importers

- CSV uses pandas with charset detection.
- XLS uses pandas with xlrd.
- XLSX uses openpyxl and pandas so formula values remain visible to validation.
- Exact aliases are mapped to canonical fields.
- Ambiguous fields are reported as candidates and require an explicit CLI column option.

## Validation

V2 validates required values, timestamps, decimal amounts, blockchain address formats, duplicate transaction hashes, and CSV/Excel formula injection. A failed batch produces no output files.

## Normalizers

- Ethereum addresses and asset contracts are lowercased.
- TRON Base58 addresses preserve their input form.
- Bitcoin addresses preserve their input form.
- All normalizers produce the same framework-independent Domain Transaction.

## Supported formats

- `.csv`
- `.xls`
- `.xlsx`

The current exports are limited to:

- `transactions_normalized.csv`
- `summary.json`

Column overrides:

```powershell
python -m crypto_investigator analyze-file transactions.csv `
  --from-column sender `
  --to-column receiver `
  --amount-column value `
  --asset-column symbol `
  --time-column datetime `
  --tx-column txid
```

## Analysis Engine

Every Analyzer accepts only canonical Domain Transactions:

`Domain Transaction -> Analyzer Factory -> Analyzer -> AnalysisResult -> data export`

Available Analyzer names:

- `summary`
- `statistics`
- `counterparty`
- `timeline`
- `flow`

The complete engine writes:

- `analysis.json`
- `summary.json`
- `counterparties.csv`
- `timeline.json`
- `timeline.csv`
- `flow.json`

Run all analyzers:

```powershell
python -m crypto_investigator analyze-all transactions.csv `
  --address 0x0000000000000000000000000000000000000000
```

Run individual analyzers:

```powershell
python -m crypto_investigator analyze-summary transactions.csv --address <ADDRESS>
python -m crypto_investigator analyze-counterparty transactions.csv --address <ADDRESS>
python -m crypto_investigator analyze-timeline transactions.csv
```

### Summary and statistics

Summary covers observation range, transaction and direction counts, active days, assets, counterparties, and daily frequency. Statistics keep incoming, outgoing, average, median, maximum, and minimum amounts separated by asset.

### Counterparty

Counterparty aggregation is relative to the optional target address. Counts, first/last interaction, relationship direction, and incoming/outgoing amount maps are emitted without combining different assets.

### Timeline

Timeline data includes daily and monthly buckets plus hourly and weekday distributions. V3 emits JSON and CSV data only.

### Flow

Flow contains address nodes and transaction edges with direction, weight, asset, and timestamp. It is a data model only: V3 includes no NetworkX, PyVis, Mermaid, HTML, or graph rendering.

## Architecture

- `core`: application composition, runtime context, and settings.
- `core/pipeline.py`: reusable pipeline orchestration.
- `core/export.py`: normalized CSV and JSON summary export.
- `domain`: framework-independent addresses, assets, transactions, counterparties, and cases.
- `importers`: file readers, field mapping, and validation.
- `normalizers`: chain-specific normalization selected through a factory.
- `analyzers`: Domain-only analyzers, result models, factory, engine, and data exporters.
- `providers`: async contracts, registry, factory, selection/fallback, adapters, and collection.
- `cache`: TTL file cache with safe keys, atomic writes, and corrupt-entry recovery.
- `plugins`: extension Protocol, Registry, and explicit Loader.
- `tools`: future tool Protocol and Registry; no tools are implemented in V1.1.
- `models` and `detection`: existing V1 domain models and identifier detection.
- `shared`: reserved for domain-neutral shared code.
- `constants`: stable application-wide constants.
- `docs`: progress, decisions, planned work, and changelog.

## Roadmap

- V1.1: extensible architecture foundation without new business features.
- V1.2: framework-independent Domain Layer.
- V2: Data Pipeline delivering CSV/XLS/XLSX import, validation, normalization, Domain Transactions, and CSV/JSON export.
- V3: Domain-only Summary, Statistics, Counterparty, Timeline, and Flow analysis.
- V4: Blockchain Provider Engine feeding V2 Pipeline and V3 Analysis.
- V5 and later: delivered as separately approved milestones.

Graph rendering, reports, AI, risk, bridges, and cross-chain features remain outside V4 scope.
