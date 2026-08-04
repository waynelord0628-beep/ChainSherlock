# ChainSherlock

ChainSherlock is a local-first blockchain transaction investigation toolkit.

**Version:** 0.1.2 (V1.2)

## V1 quick start

```powershell
pip install -e .
python -m crypto_investigator --help
python -m crypto_investigator detect 0x0000000000000000000000000000000000000000
python -m crypto_investigator providers
pytest
```

V1 includes the project foundation, typed data models, identifier detection, configuration, and CLI. Importers, analysis, providers, caching, and reports are intentionally scheduled for later versions.

## Architecture

- `core`: application composition, runtime context, and settings.
- `domain`: framework-independent addresses, assets, transactions, counterparties, and cases.
- `plugins`: extension Protocol, Registry, and explicit Loader.
- `tools`: future tool Protocol and Registry; no tools are implemented in V1.1.
- `models` and `detection`: existing V1 domain models and identifier detection.
- `shared`: reserved for domain-neutral shared code.
- `constants`: stable application-wide constants.
- `docs`: progress, decisions, planned work, and changelog.

## Roadmap

- V1.1: extensible architecture foundation without new business features.
- V1.2: framework-independent Domain Layer.
- V2: Data Pipeline delivering CSV import, normalization, Domain Transactions, and JSON export only.
- V3 and later: delivered as separately approved milestones.

Counterparty analysis, timeline, graph, providers, and other analysis remain outside V2 scope.
