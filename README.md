# ChainSherlock

ChainSherlock is a local-first blockchain transaction investigation toolkit.

## V1 quick start

```powershell
pip install -e .
python -m crypto_investigator --help
python -m crypto_investigator detect 0x0000000000000000000000000000000000000000
python -m crypto_investigator providers
pytest
```

V1 includes the project foundation, typed data models, identifier detection, configuration, and CLI. Importers, analysis, providers, caching, and reports are intentionally scheduled for later versions.
