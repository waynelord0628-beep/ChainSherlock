# Investigation Planner

The deterministic Planner stores the same `AnalysisScope` on the plan and each
analysis step.

- Full History uses explicit Provider-end pagination and required capability
  completeness, with elapsed-time and API-call warnings.
- Custom Date Range stores timezone, date boundaries and inclusive start/end.
- Quick Preview stores explicit `max_pages` and `max_records` and is never a formal
  complete-history mode.

Legacy cases without scope are planned as bounded Quick Preview. Execution passes
the saved scope to the Provider layer; adapters receive common pagination options
and do not interpret case semantics independently.

Required capabilities are Ethereum normal/token transfers, TRON native/TRC20, and
Bitcoin address transactions plus UTXO/spend information. Internal/NFT or balance
gaps remain optional limitations under the current product definition.

The Planner adds no Cross-chain, Risk/AML, commercial intelligence, V9 or Windows
packaging work.
