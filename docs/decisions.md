# Architecture Decisions

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
