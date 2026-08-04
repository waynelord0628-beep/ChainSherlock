# ChainSherlock

ChainSherlock is a local-first blockchain transaction investigation toolkit.

**Version:** 0.1.1 (V1.1)

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
- `plugins`: extension Protocol, Registry, and explicit Loader.
- `tools`: future tool Protocol and Registry; no tools are implemented in V1.1.
- `models` and `detection`: existing V1 domain models and identifier detection.
- `shared`: reserved for domain-neutral shared code.
- `constants`: stable application-wide constants.
- `docs`: progress, decisions, planned work, and changelog.

## Roadmap

- V1.1: extensible architecture foundation without new business features.
- V2 and later: delivered as separately approved milestones.

CSV import, blockchain providers, analysis, and reporting are outside V1.1 scope.
