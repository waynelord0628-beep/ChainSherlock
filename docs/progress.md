# Development Progress

## Current version

V2 — Data Pipeline Engine.

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

## Validation

- Editable installation succeeds in a clean Python 3.12 virtual environment.
- All automated tests pass.
- CLI help command runs successfully.

## Scope guard

V2 contains no Provider, Graph, Timeline, Counterparty analysis, Report, AI, Risk, Cross-chain, Bridge, or on-chain API implementation.
