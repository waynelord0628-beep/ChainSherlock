# V3 Analysis Engine Benchmark

- Python: 3.12.13
- Platform: Windows-11-10.0.26200-SP0
- Scope: Data Pipeline, Analysis Engine, and data-only export
- Method: single measured run with `time.perf_counter` and `tracemalloc`

| Dataset | Transactions | Execution Time (s) | Peak Memory (MiB) |
|---|---:|---:|---:|
| small | 10 | 0.0387 | 0.34 |
| medium | 1000 | 0.6682 | 3.43 |
| large | 10000 | 6.7167 | 31.17 |

Results are environment-specific and are intended as a regression baseline.
