# ChainSherlock

本機優先、證據可追溯的區塊鏈幣流調查平台。

ChainSherlock 將 CSV、Excel 與公開區塊鏈 Provider 的交易資料，依序轉換為標準
Domain Transaction，再進行統計分析、關係圖、規則式調查、案件管理與正式報告。
系統預設不使用 AI；啟用 AI 時，它只補充通過 grounding 與 quality gates 的專業
敘事，不會取代原始證據或確定性分析。

> 目前狀態：V8 封版階段
>
> 套件版本：`0.1.4`
>
> Python：`>=3.12`
>
> 最近離線驗收：`1455 passed, 1 skipped`，`pip check` 通過
>
> V9 與 Windows 安裝包尚未開始

## 核心原則

- **Local-first**：案件、Evidence、分析結果與報告預設保存在本機。
- **Deterministic-first**：主要事實、統計、排名與 Investigation Features 皆由
  可重複的規則式流程產生。
- **Evidence-linked**：Evidence、Execution artifacts、報告與案件套件使用
  SHA-256、相對路徑與可驗證 manifest。
- **Asset-aware**：不同資產分開統計，不將 TRX、USDT、BTC、ETH 等數值直接相加。
- **Scope-aware**：完整歷史、指定期間與快速預覽具有不同語意；部分資料不得冒充
  完整歷史。
- **Candidate is not Confirmed**：候選角色、服務型態或 Spam/Dust 判斷不會被描述成
  已確認身分或犯罪結論。
- **AI is optional**：AI 預設停用；失敗、截斷或驗證不通過時保留完整規則式報告。

## 能做什麼

| 能力 | 目前狀態 |
|---|---|
| CSV／XLS／XLSX 匯入、欄位映射與安全驗證 | 已完成 |
| Ethereum／TRON／Bitcoin 正規化 | 已完成 |
| Summary、Statistics、Counterparty、Timeline、Flow | 已完成 |
| Etherscan、Blockscout、TronGrid、Blockstream | 已完成 |
| Provider pagination、fallback、dedup、partial failure | 已完成 |
| Graph JSON、GraphML、完全離線 HTML | 已完成 |
| 規則式 Investigation Engine | 已完成 |
| Markdown、離線 HTML、DOCX、PDF 報告 | 已完成 |
| Evidence manifest、SHA-256、partial export | 已完成 |
| Grounded AI Narrative／Professional Enrichment | 可選，預設停用 |
| Case Workspace、Planner、Execution、Result、Audit | 已完成 |
| PySide6 Desktop Investigation Workbench | 已完成 |
| Windows 安裝包 | 尚未開始 |
| V9 | 尚未開始 |

ChainSherlock 是調查輔助工具，不會僅依鏈上資料直接判定詐欺、洗錢、犯罪行為、
實際控制人或法律責任。

## 安裝

建議在 Windows PowerShell 使用乾淨的 Python 3.12 虛擬環境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
pip check
```

開發與測試：

```powershell
pip install -e ".[dev]"
pytest -q -rs
```

若要重現已凍結的驗證環境：

```powershell
pip install -r requirements.lock
pip install -e .
```

`requirements.lock` 記錄 Python 與完整套件版本；`pyproject.toml` 則使用相容版本
範圍，避免把開發環境永久鎖死。

## 快速開始

### Desktop UI

直接啟動本機案件工作台：

```powershell
python -m crypto_investigator
```

或明確指定：

```powershell
python -m crypto_investigator ui
python -m crypto_investigator ui --case-root cases
```

桌面案件流程：

```text
建立案件
  -> 匯入 Evidence / 設定調查標的
  -> 選擇 Goals
  -> 產生並確認 Plan
  -> Execution
  -> Result / Investigation / Graph
  -> Narrative（可選）
  -> 四格式 Report
  -> Audit / Case Package
```

### CLI

查看所有指令：

```powershell
python -m crypto_investigator --help
```

分析本機交易檔：

```powershell
python -m crypto_investigator analyze-file transactions.csv
python -m crypto_investigator analyze-all transactions.csv --address <ADDRESS>
python -m crypto_investigator investigate-file transactions.csv --target <ADDRESS>
python -m crypto_investigator report-file transactions.csv --target <ADDRESS> --format all
```

分析公開鏈上地址：

```powershell
python -m crypto_investigator analyze-address <ADDRESS> --chain tron
python -m crypto_investigator investigate-address <ADDRESS> --chain tron
python -m crypto_investigator report-address <ADDRESS> --chain tron --format all
```

### 多層資金追蹤（開發驗收版）

`trace-address` 與既有單地址報告分開，不會改變已封版的第一層報告模板。
預設雙向追蹤 3 層，最多 5 層；USDT、TRX 分開計算，FIFO 只代表分析配對，
不代表確認鏈上同一筆資金。

```powershell
python -m crypto_investigator trace-address <ADDRESS> `
  --chain tron `
  --assets USDT,TRX `
  --depth 3 `
  --direction bidirectional `
  --minimum-amount 0.01 `
  --max-address-queries 20 `
  --max-pages-per-address 10 `
  --output output\multihop_trace
```

輸出包含 `trace_result.json`、`flow_graph.json`、`flow.graphml`、離線
`flow.html`，以及 Markdown、HTML、DOCX、PDF 報告。任何查詢、節點、紀錄或
Provider 分頁上限被觸發時，結果會標記為 `partial`，不得視為完整資金路徑。

建立離線 Graph：

```powershell
python -m crypto_investigator graph-file transactions.csv `
  --target <ADDRESS> `
  --max-nodes 100 `
  --max-edges 200
```

案件輸出與移轉：

```powershell
python -m crypto_investigator case-result <CASE_ID>
python -m crypto_investigator case-report <CASE_ID> --format all
python -m crypto_investigator case-export <CASE_ID> `
  --output output\case.chainsherlock-case.zip `
  --mode full
python -m crypto_investigator case-package-validate output\case.chainsherlock-case.zip
python -m crypto_investigator case-import output\case.chainsherlock-case.zip
```

## 資料處理架構

所有來源最終都必須進入同一條 Domain Pipeline：

```text
CSV / Excel / Blockchain Provider
                 |
                 v
       Importer / Raw Record
                 |
                 v
      Validation + Rejection
                 |
                 v
        Chain Normalizer
                 |
                 v
       Domain Transaction
                 |
        +--------+---------+
        |                  |
        v                  v
 Analysis Engine       Graph Engine
        |                  |
        +--------+---------+
                 v
      Investigation Engine
                 |
        +--------+---------+
        |                  |
        v                  v
 Deterministic Report   Optional AI Narrative
        |                  |
        +--------+---------+
                 v
       Case Result / Audit / Package
```

Provider response 不會直接進入 Analyzer。這個邊界可避免 Importer Model、API Model、
Graph Model 與案件模型混在一起，也讓 CSV 與鏈上 Provider 共用相同下游能力。

## Analysis Scope 與完整度

ChainSherlock 支援三種分析範圍：

- `full_history`：required capabilities 必須翻頁到 Provider 明確結尾，且不得因
  `max_pages` 或 `max_records` 提前停止，才可宣稱完整歷史。
- `custom_date_range`：保存起訖、timezone 與 inclusive boundaries；報告只使用
  「指定期間內」語意。
- `quick_preview`：允許有限頁數／筆數，只供預覽，不代表完整首次交易、最後交易、
  完整總額或完整交易數。

報告會分別揭露：

- retrieval completeness
- asset classification completeness
- material analysis scope
- Provider completeness
- Graph completeness
- rejected／deduplicated／failed／unclassified counts

## 支援的資料與鏈

### 檔案

- CSV：pandas + charset detection
- XLS：pandas + xlrd
- XLSX：pandas + openpyxl

Importer 會檢查必填欄位、時間、Decimal 金額、地址、重複交易與試算表公式注入。
欄位有歧義時不猜測，必須以 CLI 欄位參數明確指定。

### Provider

| 鏈 | Primary | Fallback／補充 |
|---|---|---|
| Ethereum | Etherscan | Blockscout |
| TRON | TronGrid | — |
| Bitcoin | Blockstream Esplora | — |

Provider 層提供 capability 宣告、非同步 HTTP、timeout、有限 retry、rate limit、
pagination、checkpoint、來源感知 dedup、fallback 與 partial result。

環境變數範例位於 `.env.example`：

```text
ETHERSCAN_API_KEY=
TRONGRID_API_KEY=
BLOCKSCOUT_API_URL=
BLOCKSTREAM_API_URL=https://blockstream.info/api
```

API Key 不會寫入 log、cache key、report、artifact、Audit 或 Git。

## TRON 資產處理

TRON 資料採嚴格資產分類：

- 原生 TRX：`TransferContract` 且資產為 `TRX`
- TRC10／其他資產：`TransferAssetContract`，保留原始 symbol／asset ID
- TRC20：依 token contract 與 symbol 獨立分類
- 未知項目：`unknown_tron_asset`，不得自動歸入 TRX

微額 TRX、Dust、Spam 或宣傳型資產候選不會被無聲刪除。原始 Evidence 永遠保留；
主要報告可依可逆的 materiality policy 排除低重要性項目，詳細原因與數值保留於
技術資料供人工覆核。

## Investigation Engine

V6.5 規則式調查層不使用 AI，主要提供：

- Funding source、占比、集中度與來源切換
- Operation stages、Dormancy 與 Recovery
- Counterparty concentration、Herfindahl Index、Gini、Entropy
- Local／Static／CSV Label 與候選服務型態
- Holding time、FIFO approximation
- Fixed amount、整數金額與 batch pattern
- Relationship、Behavior Summary、Observations、Conclusion Facts

輸出保持 Decimal 精度、timezone-aware datetime 與可追溯 Fact／Observation／
Evidence ID。

## Graph Engine

Graph Engine 只接受公開的 `AnalysisResult.flow`，不直接讀取 Provider raw response。

輸出：

- `flow_graph.json`
- `flow.graphml`
- `flow.html`（完全離線）

Graph 可依資產、地址、方向、日期、交易次數及最大節點／邊數篩選。Provider
完整度與 Graph 截斷狀態分開保存，避免把完整 Provider 資料誤寫成完整圖譜。

## 正式報告

目前穩定正式產品定位為「地址剖繪與第一層資金流分析報告」
（Address Profile and First-Hop Fund Flow Analysis）。它會呈現目標地址與第一層
主要來源／去向，但不會把排行組合冒充 transaction-level path，也不宣稱已完成
多層追蹤或確認最終下車點。多層追蹤目前為獨立的開發驗收產品入口，
使用真實交易 Edge、FIFO 配對、3～5 層雙向 frontier、回流／集中／分散候選、
可信 Label 停止條件與下車點候選；尚未取代穩定的第一層正式報告。

支援：

- Markdown
- 完全離線 HTML
- DOCX
- PDF
- `report_data.json`
- `evidence_manifest.json`
- `export_status.json`
- `export_errors.json`

正式報告會：

- 以案件 timezone 顯示人類可讀時間
- 依資產分章，不做跨資產加總
- 分開呈現已確認資料事實、規則式觀察與候選解釋
- 揭露資料範圍、完整度、Provider／Graph 狀態與限制
- 使用 Address Registry 保存完整可複製地址
- 將 record-level mapping 與低重要性工程資料移至技術附件
- 對 Evidence artifact 建立 SHA-256
- 在 PDF 失敗時保留其他成功格式並標記 partial

Windows 會優先使用系統標楷體輸出 CJK PDF，也可覆寫：

```powershell
$env:CHAINSHERLOCK_PDF_CJK_FONT="C:\path\to\cjk-font.ttf"
```

字型絕對路徑不會保存於正式 artifact。

## AI Narrative（可選）

AI 預設關閉。只有使用者明確啟用時才會呼叫 OpenAI-compatible Provider。

```powershell
python -m crypto_investigator narrate-investigation investigation.json `
  --output output\narrative
```

AI 只接收經壓縮與排序的 structured facts，不接收：

- raw transaction list
- 原始 Evidence 附件
- 完整 Provider response
- API Key／Authorization Header
- 完整 request body／prompt log
- 本機絕對路徑

輸出必須通過 JSON schema、numeric、citation、reference、candidate preservation、
hallucination 與禁止用語驗證。任何驗證失敗都不採用半成品，並保留完整規則式報告。

## Case、Evidence 與 Audit

V8 案件層提供：

- opaque safe `case_id`
- atomic `case.json` write
- immutable Evidence copy
- SHA-256、size、type、imported time
- 僅保存 workspace 相對路徑
- append-only hash-chain Audit Log
- schema migration 與未知欄位保留
- Planner confirmation gate
- cooperative cancellation、checkpoint、resume、bounded retry
- versioned reports
- full／report-only／deidentified case package

案件套件匯入會檢查路徑穿越、symbolic link、檔案大小、壓縮比例與 manifest hash。

## 專案結構

```text
src/crypto_investigator/
├─ core/            # Application、Context、Settings、Pipeline
├─ domain/          # Address、Asset、Transaction、Counterparty、Case
├─ importers/       # CSV／Excel／Provider raw record
├─ normalizers/     # Ethereum／TRON／Bitcoin
├─ analyzers/       # Summary／Statistics／Counterparty／Timeline／Flow
├─ providers/       # Etherscan／Blockscout／TronGrid／Blockstream
├─ graphs/          # Graph model、filter、aggregation、export
├─ investigation/   # Deterministic Investigation Features
├─ narratives/      # Grounded narrative
├─ ai/              # Optional AI provider、schema、validator、fallback
├─ reports/         # MD／HTML／DOCX／PDF／manifest
├─ cases/           # Case、Workspace、Evidence、Audit、Migration
├─ planner/         # Goals、Plan、validation、confirmation
├─ application/     # Execution、Case Result、Report、Package services
├─ services/        # Step、artifact、state adapters
├─ ui/              # PySide6 Desktop Workbench
├─ plugins/         # Plugin Protocol、Registry、Loader
├─ tools/           # Tool Protocol、Registry
└─ cli.py           # Typer CLI
```

更完整的架構與恢復上下文：

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/progress.md`](docs/progress.md)
- [`docs/decisions.md`](docs/decisions.md)
- [`docs/changelog.md`](docs/changelog.md)
- [`docs/todo.md`](docs/todo.md)
- [`docs/fund-tracing.md`](docs/fund-tracing.md)
- [`PROJECT_RECOVERY_CONTEXT.md`](PROJECT_RECOVERY_CONTEXT.md)

## 版本歷程

| 版本 | 主要成果 |
|---|---|
| V1 | CLI、設定、identifier detection 與基礎資料模型 |
| V1.1 | Core、Plugin Registry、Tool Registry、共用架構邊界 |
| V1.2 | Framework-independent Domain Layer |
| V2 | CSV／Excel Data Pipeline、Validation、Normalizer、Dependency Freeze |
| V3 | Domain-only Analysis Engine |
| V4／V4.2 | 三鏈 Provider、fallback、pagination、dedup、partial reliability |
| V5 | Graph Engine 與離線視覺化 |
| V6 | 四格式 Report Engine、Evidence manifest、partial export |
| V6.5 | Deterministic Investigation Engine |
| V7～V7.3 | Grounded Narrative、離線重建、安全 OpenAI-compatible integration |
| V8 M1～M4 | Case、Evidence、Audit、Planner、Execution、Result、Package |
| V8 M5～M8 | Desktop Workbench、離線 Evidence 與真實 Provider Execution |
| V8 封版修正 | Full History scope、TRON 資產分類、專業報告與一致性驗收 |

目前不自行開始 V9，也尚未進行 Windows 安裝包封裝。

## 測試

```powershell
pytest -q -rs
python -m pip check
```

真實 Provider 與 AI integration tests 必須由人工明確配置；一般測試預設離線，
不會產生額外 API 成本。

## License

目前 repository 尚未宣告正式授權條款。在加入 License 前，請勿假設本專案已採用
任何開源授權。
