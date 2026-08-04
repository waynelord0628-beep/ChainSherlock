# ChainSherlock

ChainSherlock is a local-first blockchain transaction investigation toolkit.

**Version:** 0.1.2 (V1.2)

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
pytest
```

V2 adds a reusable Data Pipeline. It imports transaction files, validates every row, normalizes chain-specific representation into Domain Transactions, and exports normalized data. It does not perform transaction analysis.

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

## Architecture

- `core`: application composition, runtime context, and settings.
- `core/pipeline.py`: reusable pipeline orchestration.
- `core/export.py`: normalized CSV and JSON summary export.
- `domain`: framework-independent addresses, assets, transactions, counterparties, and cases.
- `importers`: file readers, field mapping, and validation.
- `normalizers`: chain-specific normalization selected through a factory.
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
- V3 and later: delivered as separately approved milestones.

Counterparty analysis, timeline, graph, providers, and other analysis remain outside V2 scope.
