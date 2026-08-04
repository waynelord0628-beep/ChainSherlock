# V8 Milestone 8 Provider Execution Validation

Validation date: 2026-08-04

## Scope

- Real public Ethereum, TRON and Bitcoin Provider requests.
- `max_pages=1`, `max_records=20`, `retries=0`, cache enabled.
- Provider StepHandler through V8 Case Execution, followed by Graph and deterministic
  Investigation.
- No AI, paid model, commercial intelligence API or cross-chain processing.

## Results

| Chain | Provider result | Transactions | Execution | Graph | Investigation |
|---|---|---:|---|---|---|
| Ethereum | Etherscan authentication error; Blockscout fallback for address/token; internal unavailable | 40 | partial | completed | completed |
| TRON | TronGrid bounded at 20 address and 20 token records | 40 | partial | completed | completed |
| Bitcoin | Blockstream bounded at 20 address records | 20 | partial | completed | completed |

All three executions were partial because the acceptance intentionally stopped at one
page. No execution had a fatal failure. Partial Provider data remained available to
Graph and Investigation.

## Reliability and safety

- Ethereum primary/fallback status and unresolved internal capability were preserved.
- TRON and Bitcoin truncation were explicitly recorded.
- Duplicate flow keys: Ethereum 0, TRON 0, Bitcoin 0.
- API key, Authorization header and local absolute-path scan matches: 0.
- Provider status, errors and rejected records were registered as immutable
  execution artifacts with relative paths and SHA-256.
- Raw validation artifacts remain ignored under `output/` and are not committed.
