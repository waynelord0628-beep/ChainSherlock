# V4 Provider Benchmark

Offline benchmark for 100, 10,000, and 100,000 mock Provider records. It measures fetch simulation, parsing, source-aware deduplication, the existing V2 Pipeline, the existing V3 Analysis Engine, and peak traced memory.

```powershell
python bench/provider_benchmark.py
```

It performs no live API calls and is not a performance gate.

Validated on Python 3.12.13:

| Records | Fetch | Parse | Dedup | Pipeline | Analysis | Peak memory |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0009s | 0.0000s | 0.0001s | 0.0046s | 0.0035s | 0.27 MiB |
| 10,000 | 0.1057s | 0.0000s | 0.0094s | 0.5121s | 0.3692s | 26.09 MiB |
| 100,000 | 1.8171s | 0.0000s | 0.1781s | 7.2872s | 4.5339s | 259.30 MiB |
