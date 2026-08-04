# ChainSherlock

> 目前版本：V6.5 Investigation Feature Engine

V6.5 在既有分析、圖譜與報告流程之上加入可重複、可驗證的規則式調查特徵。它不使用 AI、LLM、風險分數或犯罪判斷。

```text
AnalysisResult + GraphResult + Provider completeness + Local labels
                              |
                              v
                Investigation Feature Engine
                              |
                              v
                    InvestigationResult
```

主要指令：

```powershell
python -m crypto_investigator investigate-file FILE --target ADDRESS
python -m crypto_investigator investigate-address ADDRESS --chain tron
python -m crypto_investigator investigate-tx TX_HASH --chain ethereum
python -m crypto_investigator labels-import LABELS.csv
python -m crypto_investigator labels-check ADDRESS --chain ethereum
```

輸出包含 `investigation.json`、`investigation_evidence.json`、
`observations.json`、`conclusion_facts.json` 與 `label_matches.json`。
金額依資產分開計算，JSON 保留 Decimal 與 timezone-aware datetime。

ChainSherlock 是一套本機優先（local-first）的區塊鏈交易與幣流調查工具。

**目前里程碑：** V5 Graph Engine

**套件版本：** 0.1.2

## 安裝

建議使用 Python 3.12 建立虛擬環境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

若要重現已驗證的完整相依環境：

```powershell
pip install -r requirements.lock
pip install -e .
```

## 快速開始

```powershell
python -m crypto_investigator --help
python -m crypto_investigator detect 0x0000000000000000000000000000000000000000
python -m crypto_investigator analyze-file transactions.csv
python -m crypto_investigator providers
python -m crypto_investigator analyze-address <ADDRESS>
python -m crypto_investigator analyze-tx <TX_HASH> --chain ethereum
pytest
```

目前版本包含：

- V2 Data Pipeline：匯入交易檔案、逐筆驗證、依鏈別正規化為 Domain Transaction，並輸出標準化資料。
- V3 Analysis Engine：只接受 Domain Transaction，提供摘要、統計、交易對手、時間軸與 Flow 資料分析。
- V4 Blockchain Provider Engine：透過 Etherscan、Blockscout、TronGrid 與 Blockstream Esplora 取得鏈上資料。
- V4.2 Reliability Fixes：強化 fallback、分頁硬限制、Bitcoin 未確認交易與部分資料處理。
- V5 Graph Engine：將 V3 Flow Data 建立為可篩選、可聚合且具安全上限的交易關係圖。

Provider 資料不能直接進入 Analyzer，必須依序通過：

`Provider -> Raw Record -> Validation -> Normalization -> Domain Transaction -> Analysis Engine`

## 區塊鏈 Provider

- Ethereum：Etherscan 為 primary，Blockscout 為 fallback。
- TRON：TronGrid。
- Bitcoin：Blockstream Esplora。
- 支援 capability 宣告、健康檢查、非同步 HTTP、重試、rate limit、分頁限制與部分失敗。
- 使用來源感知的 deduplication，避免同一筆 transfer 被重複計算。
- 使用 `.env.example` 所列的環境變數設定 API Key；密鑰不會寫入 log、cache key 或輸出檔。

地址分析範例：

```powershell
python -m crypto_investigator analyze-address <ADDRESS> `
  --chain ethereum `
  --max-pages 10 `
  --max-records 1000 `
  --output output\investigation
```

單筆交易分析：

```powershell
python -m crypto_investigator analyze-tx <TX_HASH> --chain bitcoin
```

Provider 工作流會額外輸出：

- `provider_status.json`
- `provider_errors.json`
- `rejected_records.json`
- `raw/`

`analysis.json` metadata 會以 `complete`、`partial` 或 `failed` 表示資料完整度。

## Graph Engine

Graph Engine 只接受 V3 公開的 `AnalysisResult.flow`，不直接讀取 CSV、Provider Raw Record、Importer 或 Normalizer。

檔案建立圖：

```powershell
python -m crypto_investigator graph-file transactions.csv `
  --target 0x0000000000000000000000000000000000000000 `
  --max-nodes 100 `
  --max-edges 200
```

地址建立圖：

```powershell
python -m crypto_investigator graph-address <ADDRESS> `
  --chain ethereum `
  --max-records 1000 `
  --top-counterparties 30
```

Graph filter 支援：

- top counterparties 與 minimum transaction count
- include／exclude asset
- include／exclude address
- incoming-only／outgoing-only
- date range
- maximum nodes／edges
- transactions、interactions 或指定資產排序

Graph 輸出：

- `flow_graph.json`：完整 GraphResult，可 round-trip。
- `flow.graphml`：可由 NetworkX 重新載入，也可供 Gephi 使用。
- `flow.html`：PyVis inline assets 產生的離線互動圖。

所有圖形輸出都保留不同資產的金額分離。Target node 不會因安全限制被截斷，HTML label 與 tooltip 會先 escape，且 Provider credential 不會寫入 HTML。

## Data Pipeline

所有支援的資料來源都遵循同一方向：

`Raw Data -> Importer -> Validation -> Normalizer -> Domain Transaction -> Export`

檔案型 V2 Pipeline 採嚴格整批驗證：任何一筆資料不合法，整批會在 Domain conversion 與輸出之前停止。Provider 工作流則採逐筆驗證，保留有效資料並將無效資料寫入 `rejected_records.json`。

Importer 不負責決定鏈別行為；鏈別正規化由 `NormalizerFactory` 統一選擇。

## Importer 與支援格式

- `.csv`：使用 pandas，並支援字元編碼偵測。
- `.xls`：使用 pandas 與 xlrd。
- `.xlsx`：使用 openpyxl 與 pandas，保留公式內容供安全驗證。
- 欄位只使用明確 alias 對應；有歧義時要求使用 CLI 選項指定來源欄位。

欄位覆寫範例：

```powershell
python -m crypto_investigator analyze-file transactions.csv `
  --from-column sender `
  --to-column receiver `
  --amount-column value `
  --asset-column symbol `
  --time-column datetime `
  --tx-column txid
```

標準化輸出：

- `transactions_normalized.csv`
- `summary.json`

## Validation

V2 會驗證：

- 必填欄位
- timestamp
- 十進位金額
- Ethereum、TRON 與 Bitcoin 地址格式
- 重複交易
- CSV／Excel formula injection

Bitcoin 未確認交易只有在來源 metadata 明確標記 `confirmed = false` 時，才允許 `timestamp = null`。系統不會製造 `1970-01-01` 或目前時間作為替代值。

## Normalizer

- Ethereum 地址與 token contract 統一轉為小寫。
- TRON Base58 地址保留原始表示。
- Bitcoin 地址保留原始表示。
- 所有 Normalizer 都產生相同且不依賴框架的 Domain Transaction。

## Analysis Engine

所有 Analyzer 只接受標準 Domain Transaction：

`Domain Transaction -> Analyzer Factory -> Analyzer -> AnalysisResult -> Data Export`

可用 Analyzer：

- `summary`
- `statistics`
- `counterparty`
- `timeline`
- `flow`

執行全部分析：

```powershell
python -m crypto_investigator analyze-all transactions.csv `
  --address 0x0000000000000000000000000000000000000000
```

分別執行：

```powershell
python -m crypto_investigator analyze-summary transactions.csv --address <ADDRESS>
python -m crypto_investigator analyze-counterparty transactions.csv --address <ADDRESS>
python -m crypto_investigator analyze-timeline transactions.csv
```

完整輸出：

- `analysis.json`
- `summary.json`
- `counterparties.csv`
- `timeline.json`
- `timeline.csv`
- `flow.json`

### Summary 與 Statistics

Summary 包含觀察期間、交易數、方向統計、活躍天數、資產、交易對手與每日頻率。Statistics 依資產分開計算流入、流出、平均、中位數、最大值及最小值，不會將不同資產的金額相加。

### Counterparty

Counterparty 以選填的目標地址為基準，統計互動次數、首次／最後互動時間、關係方向，以及依資產分開的流入與流出金額。

### Timeline

Timeline 提供每日、每月、每小時與星期分布。缺少 timestamp 的未確認 Bitcoin 交易不會進入 Timeline，但仍保留在 Summary、Statistics、Counterparty 與 Flow。

### Flow

Flow 包含地址節點與交易邊，記錄方向、權重、資產及 timestamp。目前只輸出資料模型，不包含 NetworkX、PyVis、Mermaid、HTML 或圖形渲染。

## 架構

- `core`：應用程式組裝、執行環境與設定。
- `core/pipeline.py`：可重用的 Data Pipeline。
- `core/export.py`：標準化 CSV 與 JSON 輸出。
- `domain`：不依賴框架的地址、資產、交易、交易對手與案件實體。
- `importers`：檔案讀取、欄位映射與驗證。
- `normalizers`：由 Factory 選擇的鏈別正規化。
- `analyzers`：Domain-only Analyzer、結果模型、Factory、Engine 與資料輸出。
- `providers`：非同步 Provider contract、Registry、Factory、fallback 與鏈別 adapter。
- `graphs`：Graph Domain Model、Builder、Filtering、NetworkX adapter 與 JSON／GraphML／HTML export。
- `cache`：具有安全 key、TTL、atomic write 與損毀恢復的檔案快取。
- `plugins`：Plugin Protocol、Registry 與明確 Loader。
- `tools`：預留的 Tool Protocol 與 Registry，目前沒有實作 Tool。
- `shared`：預留給不依賴 Domain 的共用程式。
- `constants`：全域穩定常數。
- `docs`：開發進度、架構決策、待辦與變更紀錄。

核心依賴方向：

```text
Blockchain API / CSV / Excel
            |
            v
Importer -> Validation -> Normalizer
            |
            v
     Domain Transaction
            |
            v
      Analysis Engine
```

Domain Layer 不依賴 Provider、HTTP client、Importer、Analyzer、圖形套件或 AI。

## Roadmap

- V1.1：可擴充架構基礎，不新增業務功能。
- V1.2：不依賴框架的 Domain Layer。
- V2：CSV／XLS／XLSX Data Pipeline、驗證、正規化與標準輸出。
- V3：Domain-only Summary、Statistics、Counterparty、Timeline 與 Flow 分析。
- V4：Blockchain Provider Engine，串接既有 V2 Pipeline 與 V3 Analysis。
- V4.2：Provider fallback、分頁硬限制、Bitcoin mempool timestamp 與部分資料可靠性。
- V5：Graph Model、Graph Builder、Filtering、GraphML、JSON 與 offline HTML。
- V5 之後：依核准的獨立 milestone 逐步開發。

## V6 正式報告

```powershell
python -m crypto_investigator report-file data.csv --target <ADDRESS> --format all
python -m crypto_investigator report-address <ADDRESS> --format all
python -m crypto_investigator report-tx <TX_HASH> --chain ethereum --format all
```

支援 Markdown、離線 HTML、DOCX 與 PDF，並一律產生 `report_data.json`、`evidence_manifest.json`、`export_status.json` 與 `export_errors.json`。PDF 中文需先設定本機字體：

```powershell
$env:CHAINSHERLOCK_PDF_CJK_FONT="C:\Windows\Fonts\your-cjk-font.ttf"
```

未設定字體時 PDF 會明確失敗，但其他成功格式仍保留，整體狀態為 `partial`。報告會揭露資料完整度、Provider 缺口、被拒絕紀錄與證據 SHA-256；不輸出 API Key、Authorization header 或本機絕對路徑。不同資產只分別呈現，不做跨資產加總或估值。

V6 不包含 AI、Risk／AML 評分、Bridge、Cross-chain、OSINT、Web UI 或錢包操作。
# V7：AI 調查敘事

ChainSherlock V7 新增 grounded、evidence-linked 的調查敘事層。AI 預設關閉，且只接收
V6.5 `InvestigationResult` 壓縮後的結構化摘要；不讀取原始交易、CSV/Excel 或 Provider
raw response，也不進行犯罪、洗錢、詐欺、身分或風險判定。

```powershell
python -m crypto_investigator narrate-investigation investigation.json --output output/narrative
python -m crypto_investigator narrate-file transactions.csv --target ADDRESS --output output/narrative
python -m crypto_investigator narrate-address ADDRESS --output output/narrative
```

只有明確加入 `--ai` 才會呼叫外部 OpenAI-compatible provider。設定 provider/model 時請將
API key 放入環境變數，不要貼入命令、報告或提交至 Git。可用 `--privacy-mode strict`,
`standard`（預設）或 `off`；即使為 `off` 仍會遮罩 secrets 與本機絕對路徑。

V7 產生 `narrative_input.json`、`narrative.json`、`narrative_validation.json`、
`ai_usage.json`、`prompt_manifest.json`、`ai_status.json` 與 `ai_errors.json`。
無 API key、timeout、無效 JSON、引用或數字驗證失敗時，報告會保留並改用 deterministic
fallback。AI 內容進入報告前必須通過 schema、claim、citation、numeric 與禁止用語驗證，
且預設顯示「AI 內容尚未經人工確認」。使用 `--ai-max-tokens` 與
`--ai-max-input-chars` 控制 token/輸入；未設定價格時 estimated cost 為 `null`。

## V7.1 離線重建與模型驗收

`narrate-investigation` 現在可直接讀取 `investigation.json`、
`narrative_input.json` 或 `narrative.json` 並以 `--report` 離線重建報告；不會重新呼叫
Provider、讀取原始 CSV/Excel 或依賴 AnalysisResult。artifact 未保存的欄位會標記
`unavailable`，不會補造。

真實模型只能由人工明確執行：

```powershell
python -m crypto_investigator validate-ai investigation.json `
  --provider openai-compatible --model MODEL --runs 3 `
  --privacy-mode standard --output output/real_ai_validation
```

API Key 僅能由 `CHAINSHERLOCK_AI_API_KEY` 環境變數提供。指令輸出
`real_ai_validation.json`，不保存 Key；無 Key 時不會送出請求。Prompt 提供
`standard` 與內部 deterministic `compact` 模式，compact 保留 Conclusion Facts、
重要 Observations、完整度、限制與必要 Evidence IDs，同時移除重複欄位。
