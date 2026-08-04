# Development Progress

## Current version

V1.2 — framework-independent Domain Layer.

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

## Validation

- Editable installation succeeds in a clean Python 3.12 virtual environment.
- All automated tests pass.
- CLI help command runs successfully.

## Scope guard

V1.2 adds no CSV import, providers, transaction analysis, reporting, or other business functionality. V2 is limited to `CSV -> Importer -> Normalizer -> Domain Transaction -> JSON Export`.
