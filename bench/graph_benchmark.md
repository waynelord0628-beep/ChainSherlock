# V5 Graph Benchmark

離線建立 100、10,000 與 100,000 筆 Domain Transactions，量測 Graph build、filter、NetworkX conversion、JSON／GraphML／HTML export、peak memory 與輸出大小。

```powershell
python bench/graph_benchmark.py
```

Large case 的輸入維持 100,000 筆，但 export 固定套用 `maximum_nodes=100` 與 `maximum_edges=200`。

Python 3.12.13 驗證結果：

| Records | Build | Filter | NetworkX | JSON | GraphML | HTML | Peak memory | Output |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.0076s | 0.0026s | 0.0040s | 0.0098s | 0.1929s | 0.0960s | 12.66 MiB | 783.69 KiB |
| 10,000 | 0.1118s | 0.0201s | 0.0136s | 0.0285s | 0.0411s | 0.0904s | 8.77 MiB | 1097.95 KiB |
| 100,000 | 0.8702s | 0.0286s | 0.0420s | 0.0720s | 0.0729s | 0.0985s | 9.60 MiB | 2190.03 KiB |
