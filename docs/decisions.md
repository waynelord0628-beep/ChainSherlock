# Architecture Decisions

## ADR-001: Explicit composition root

`Application` owns runtime registries and constructs a shared `Context`. This keeps wiring separate from domain code.

## ADR-002: Protocol-based extension points

Plugins and tools use Python Protocols so future implementations are structurally typed and do not require inheritance.

## ADR-003: Explicit plugin loading

Plugins are loaded only from module paths supplied by the caller. V1.1 performs no package scanning or automatic discovery.

## ADR-004: Backward-compatible settings name

`Settings` is the canonical configuration model. `AppConfig` remains an alias so V1 imports continue to work.

