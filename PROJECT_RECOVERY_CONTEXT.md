# ChainSherlock 專案恢復上下文

> 建立目的：在原 ChatGPT 專案對話遺失後，以目前 Git、程式碼、測試與文件
> 重建可驗證的開發上下文。本文件不代表新增功能，也不取代程式碼。
>
> 盤點日期：2026-08-04（Asia/Taipei）
>
> 專案：ChainSherlock／Python package `crypto_investigator`
>
> 目前分支：`main`
>
> 盤點基準 Commit：`48d3b66b55a6838f254003369384233a29c59cf1`

## 1. 專案定位與目前版本

ChainSherlock 是本機優先（local-first）的區塊鏈交易與幣流調查工具。資料處理
主路徑為：

```text
CSV / Excel / Blockchain Provider
    -> Importer / Raw Record
    -> Validation
    -> Chain Normalizer
    -> Domain Transaction
    -> Analysis
    -> Graph / Investigation
    -> Narrative / Report
    -> V8 Case Workspace / Package / Desktop UI
```

`pyproject.toml` 的實際套件版本為 `0.1.4`，Python 要求為 `>=3.12`。目前 Git
歷史已完成 V1、V1.1、V2、V3、V4、V4.2、V5、V6、V6.5、V7、V7.1、V7.2
及 V8 Milestone 1～6。尚未開始 V9。

README 頂部已記錄 V8 Milestone 6，但中段仍殘留「目前版本 V6.5／V5」及
`0.1.2` 等舊版文字。這是文件一致性問題，不代表程式已降版。

## 2. 目錄與模組架構

### 2.1 Repository 根目錄

```text
ChainSherlock/
├─ benchmarks/              # V4～V8 的離線效能基準
├─ config/                  # 預設設定
├─ docs/                    # architecture、decisions、progress、todo、UI 與報告文件
├─ examples/                # CSV／Excel／label 範例
├─ scripts/                 # 驗收與輔助腳本
├─ src/crypto_investigator/ # 主要 Python package
├─ templates/               # 報告模板／資產
├─ tests/                   # unit、integration、UI 與 recorded fixture
├─ pyproject.toml           # 套件 metadata、相依套件、pytest 設定
├─ requirements.lock        # Python 3.12.13 完整凍結版本
└─ README.md
```

### 2.2 `src/crypto_investigator` 模組

| 模組 | 目前責任 | 主要檔案 |
|---|---|---|
| `core` | Application、Context、Settings、Pipeline 與 export 基礎介面 | `application.py`, `context.py`, `settings.py`, `pipeline.py` |
| `domain` | 與 importer/API/graph 解耦的領域模型 | `address.py`, `asset.py`, `transaction.py`, `counterparty.py`, `case.py`, `metadata.py` |
| `plugins` | Plugin Protocol、Registry、Loader；目前未內建業務 Plugin | `protocol.py`, `registry.py`, `loader.py` |
| `tools` | Tool Protocol、Registry；目前未內建 Tool | `protocol.py`, `registry.py` |
| `shared`, `constants` | 共用程式與常數的保留邊界 | `__init__.py` |
| `detection` | 地址／交易雜湊鏈別與型別偵測 | `identifier.py` |
| `importers` | CSV、Excel、Provider raw record 匯入、mapping 與逐列驗證 | `csv_importer.py`, `excel_importer.py`, `provider.py`, `mapping.py`, `validator.py` |
| `normalizers` | Ethereum、TRON、Bitcoin raw record 正規化 | `ethereum.py`, `tron.py`, `bitcoin.py` |
| `providers` | Provider contract、HTTP、Registry、fallback、pagination、dedup、輸出 | `base.py`, `http.py`, `registry.py`, `selection.py`, `pagination.py`, `dedup.py`, `service.py` |
| `providers/ethereum` | Etherscan primary、Blockscout fallback | `etherscan.py`, `blockscout.py` |
| `providers/tron` | TronGrid | `trongrid.py` |
| `providers/bitcoin` | Blockstream Esplora | `blockstream.py` |
| `cache` | Provider/AI 可重現的本機檔案 cache primitives | `file_cache.py`, `keys.py`, `models.py` |
| `analyzers` | Summary、Statistics、Counterparty、Timeline、Flow 與 analysis orchestration | `engine.py`, `summary.py`, `statistics.py`, `counterparty.py`, `timeline.py`, `flow.py` |
| `graphs` | Graph 建立、篩選、聚合、樣式、NetworkX、JSON/GraphML/離線 HTML 匯出 | `builder.py`, `filtering.py`, `aggregation.py`, `styling.py`, `html_renderer.py` |
| `investigation` | V6.5 deterministic feature engine | `feature_engine.py`, `funding.py`, `dormancy.py`, `stages.py`, `patterns.py`, `relationships.py`, `observations.py`, `conclusion_facts.py` 等 |
| `labels` | Local/static/CSV label registry | `registry.py` |
| `ai` | AI provider abstraction、OpenAI-compatible request、compact prompt、cache、fallback、schema validation、redaction | `provider.py`, `prompt_builder.py`, `input_compactor.py`, `schema.py`, `validator.py`, `fallback.py` |
| `narratives` | grounded narrative model、composer、citation 與 validation | `engine.py`, `composer.py`, `models.py`, `validation.py`, `export.py` |
| `reports` | ReportDocument、composition、Markdown/HTML/DOCX/PDF/JSON、evidence manifest | `composer.py`, `models.py`, `markdown_exporter.py`, `html_exporter.py`, `docx_exporter.py`, `pdf_exporter.py` |
| `cases` | V8 Case、Workspace、Evidence、Audit、Migration、Result、Package、Import/Export | `models.py`, `workspace.py`, `repository.py`, `evidence.py`, `audit.py`, `migration.py`, `results.py`, `export.py`, `importer.py` |
| `planner` | V8 deterministic InvestigationGoal/Plan/Step 與 validation | `goals.py`, `models.py`, `engine.py`, `rules.py`, `validation.py`, `service.py` |
| `application` | V8 Execution 與 Case Result/Report/Package application services | `execution_service.py`, `execution_models.py`, `execution_registry.py`, `case_result_service.py`, `case_report_service.py`, `case_package_service.py` |
| `services` | Step dispatch、artifact/state、case aggregation、narrative/export adapters | `step_dispatcher.py`, `artifact_service.py`, `execution_state_service.py`, `case_artifact_aggregator.py` |
| `ui` | PySide6 desktop workbench、Wizard、state、services、worker、models、widgets | `app.py`, `main_window.py`, `case_wizard.py`, `theme.py`, `services/`, `workers/`, `widgets/` |
| `models` | V1～V4 legacy/public Pydantic transport models | `address.py`, `transaction.py`, `analysis.py`, `counterparty.py`, `token.py` |
| `utils` | 地址驗證與 TRON/analysis 小型工具 | `address_validation.py`, `tron.py`, `analysis.py` |
| `cli.py` | Typer CLI 入口及 V2～V8 指令 | `cli.py` |
| `__main__.py` | 無參數啟動 UI；有參數交給 CLI | `__main__.py` |

## 3. 已完成的功能與實際檔案

### V1／V1.1：基礎架構

- CLI、設定、logging、identifier detection：`cli.py`, `config.py`,
  `logging_config.py`, `detection/identifier.py`。
- Plugin Protocol/Registry/Loader：`plugins/`。
- Tool Protocol/Registry：`tools/`。
- Core Application/Context/Settings：`core/`。
- framework-independent Domain Layer：`domain/`。
- 對應 Commit：`b312d91`, `fac958c`, `b93eddd`。

### V2：Data Pipeline

- CSV／Excel importer、encoding、欄位 mapping、rejected rows、normalizer、Domain
  Transaction、JSON export：`importers/`, `normalizers/`, `core/pipeline.py`。
- pandas/openpyxl/xlrd 等依賴已列入 `pyproject.toml`。
- `requirements.lock` 記錄 Python 與完整版本。
- 對應 Commit：`c2e333a`。

### V3：Analysis Engine

- Summary、statistics、counterparty、timeline、flow，且輸入使用 Domain
  Transaction：`analyzers/`。
- 對應 Commit：`aac03ad`。

### V4／V4.2：Blockchain Provider

- Etherscan、Blockscout fallback、TronGrid、Blockstream。
- async HTTP、timeout/retry、rate limit、pagination hard limits、source-aware
  dedup、partial result 與 provider status。
- 實作：`providers/`；測試：`test_ethereum_providers.py`,
  `test_tron_bitcoin_providers.py`, `test_provider_reliability_v42.py`。
- 對應 Commit：`279e906`, `8a11657`。

### V5：Graph Engine

- 交易 flow graph、filter/aggregation、stage/funding styling、JSON、GraphML、
  完全離線 HTML。
- 實作：`graphs/`；測試：`test_graph_builder_v5.py`,
  `test_graph_exports_v5.py`, `test_graph_cli_v5.py`。
- 對應 Commit：`e8647bf`。

### V6：Report Engine

- Markdown、離線 HTML、DOCX、PDF、`report_data.json`,
  `evidence_manifest.json`, `export_status.json`, `export_errors.json`。
- DOCX 字型規則：一般內容中文標楷體；英文與數字 Times New Roman；表格中文
  標楷體；表格英文與數字 Consolas。
- Evidence SHA-256、相對路徑、安全 escaping、partial export。
- 實作：`reports/`；測試：`test_reports_v6.py`。
- 對應 Commit：`d2849e8`, `70035ab`。

### V6.5：Deterministic Investigation Engine

- Funding source、operation stage、dormancy/recovery、counterparty concentration、
  local/static/CSV exchange labels、rule-based service candidate、fund distribution、
  transfer patterns、relationships、behavior summary、observations、conclusion facts。
- 不使用 AI/LLM，不輸出犯罪、詐欺或洗錢確定判斷。
- 實作：`investigation/`；測試：`test_investigation_v65.py`。
- 對應 Commit：`18cd61f`, `3561bf4`。

### V7／V7.1／V7.2：Grounded Narrative

- NarrativeInput/Result、provider abstraction、deterministic fallback、facts/
  observations/evidence grounding、numeric/citation/hallucination validation。
- `investigation.json`、`narrative_input.json` 或 `narrative.json` 可離線重建；
  缺資料時標示 unavailable，不回呼 Provider。
- standard/compact prompt、deterministic ordering、cache、OpenAI-compatible error
  redaction、strict structured output parsing。
- 實作：`ai/`, `narratives/`；測試：`test_v7_ai_narratives.py`，
  recorded fixture：`tests/fixtures/v72_chat_completions_sanitized.json`。
- 對應 Commit：`7cc05b3`, `111ade0`, `c2db8cb`, `ec720ba`。

### V8 Milestone 1：Case Foundation

- safe opaque `case_id`、CaseRecord、CaseStatus、Case Workspace。
- Evidence immutable import、SHA-256、size、media type、timezone-aware imported_at、
  正式紀錄只存 workspace-relative path。
- repository atomic write、recoverable delete/archive/duplicate 底層服務。
- append-only、redacted、SHA-256 hash-chain Audit Log。
- 舊版 `case.json` migration 且未知欄位不靜默丟失。
- 實作：`cases/models.py`, `workspace.py`, `repository.py`, `evidence.py`,
  `audit.py`, `migration.py`, `storage.py`。
- 測試：`tests/unit/test_cases_foundation.py`。
- Commit：`73ed66d050b26f8cc2cb932644410f9533dbd2b5`。

### V8 Milestone 2：Investigation Planner

- InvestigationGoal、InvestigationPlan、PlanStep、requirements/warnings/
  confirmation、deterministic rules、dependency/order/capability validation。
- Plan persistence 與 audit；不執行 Provider 或分析。
- 實作：`planner/`；測試：`tests/unit/test_planner_v8.py`。
- Commit：`9da97a0e03fad9f6494dc3b41fb4034047a3e09c`。

### V8 Milestone 3：Execution Service

- registry-based StepHandler contract、CaseExecution/StepExecution、events、
  checkpoint、artifact manifest、resume、bounded retry、cooperative cancellation。
- fatal/recoverable/partial/unsupported/cancelled/manual-review policy。
- immutable artifact registration、relative path、SHA-256/integrity verification。
- 實作：`application/execution_*`, `services/artifact_service.py`,
  `services/execution_state_service.py`, `services/step_dispatcher.py`。
- 測試：`tests/unit/test_execution_v8.py`。
- Commit：`5340e4035b8e4141c73d33e78dfc27b0a84d1142`。

### V8 Milestone 4：Case Output

- Execution artifacts 聚合為 `CaseResult`。
- deterministic narrative、Case report、版本化輸出、full/report_only/
  deidentified packages。
- package manifest SHA-256，import 前檢查 traversal、symlink、size、
  compression ratio、hash；不覆寫既有案件。
- 實作：`cases/results.py`, `package.py`, `export.py`, `importer.py`,
  `deidentification.py`, `application/case_*_service.py`,
  `services/case_*`。
- 測試：`tests/unit/test_case_output_v8.py`。
- Commit：`bee9c17ab2d0a6421b2fa152c178898d9c5c099a`。

### V8 Milestone 5：Desktop Case Workbench

- PySide6 本機工作台、案件清單/建立、Evidence、Goals、Planner、Execution、
  Result、Investigation、既有 Graph、Narrative、Report、Audit、Settings。
- QRunnable/QThreadPool 背景 worker、cooperative cancellation、AI 預設關閉。
- 實作：`ui/`；測試：`tests/ui/test_desktop_ui_v8.py`,
  `tests/integration/test_desktop_case_flow_v8.py`。
- Commit：`8d7519e281cd3c854ec469d558aed4fd1fb4d7a4`。

### V8 Milestone 6：Desktop Investigation Workflow Redesign

- 五步驟 Case Wizard、workflow navigation、next action、human-readable Plan
  cards、Execution timeline、Result Dashboard、Investigation/Counterparty/Graph/
  Narrative/Report/Audit/Settings 狀態頁。
- 視覺狀態均有文字，Confirmed/Observation/Candidate 不混用，不同資產不加總。
- 實作主要集中在 `ui/main_window.py`, `ui/case_wizard.py`, `ui/theme.py`,
  `ui/labels.py`, `ui/widgets/`。
- 測試：`tests/ui/test_desktop_workflow_m6.py`。
- Commit：`48d3b66b55a6838f254003369384233a29c59cf1`。

## 4. 未完成、部分完成或疑似問題

以下均以目前程式與文件可確認的狀態記錄：

1. **Execution handler 實際接線仍是部分完成。** Execution Service 與 UI 已存在，
   但 UI 預設 registry 沒有把 V2～V7 adapters 註冊為正式 StepHandler；沒有注入
   handler 時會安全阻擋並顯示「No execution handlers configured」。整合測試使用
   mock handler，因此不等於 UI 已完成真實 Provider 端到端執行。
2. **Provider UI 驗收仍是 mock。** Settings 顯示由環境管理的 credential 狀態，
   但目前沒有從 UI 執行真實 Provider connection test 的完整驗收。
3. **Graph UI 是既有 artifact viewer。** 僅載入案件 workspace 內既有
   `flow.html`；不在 UI 內建立 Graph，也未實作 node-click 與其他頁面的聯動。
4. **Narrative UI 不自動呼叫真實 AI。** AI 預設 disabled，頁面揭露
   deterministic fallback/status；真實模型整合測試預設依設定 skip。
5. **Report UI 預覽較簡化。** 目前主要列出版本、格式、completeness 與 export
   status，不是完整的 rich report editor/reviewer workflow；外部 reviewer 身分、
   簽核與批准流程未完成。
6. **Counterparty UI 為基礎呈現。** 資料取決於既有 public artifacts；
   專用深入篩選、context actions 與跨頁互動尚未實作。
7. **Windows 發佈尚未完成。** 沒有 PyInstaller/Nuitka installer、code signing、
   auto-update 或正式 Windows package 指令。`case-export` 是案件套件，不是應用程式
   installer。
8. **PDF CJK 字型是部署條件。** Windows 會自動偵測系統標楷體，也可用
   `CHAINSHERLOCK_PDF_CJK_FONT` 覆寫；找不到時其他輸出保留，PDF 失敗應被
   記錄為 partial export。
9. **README 版本資訊不一致。** 頂部為 V8 Milestone 6，但中段殘留 V5/V6.5 與
   package 0.1.2；實際 package 為 0.1.4。
10. **部分 UI 組裝集中。** `ui/pages/__init__.py` 幾乎是 namespace，
    `main_window.py` 承擔大量頁面組裝。這是目前實況；本輪不判定需要重構。
11. **V9、Cross-chain、Risk/AML、商業 API 與 Web UI 均未開始。**

## 5. 本輪與先前修改檔案

### 本輪（恢復文件）

- 建立 `PROJECT_RECOVERY_CONTEXT.md`。
- 未修改任何既有程式、測試、設定或文件。

### V8 先前變更範圍

- Milestone 1：`src/crypto_investigator/cases/` foundation、
  `tests/unit/test_cases_foundation.py` 與對應 docs。
- Milestone 2：`src/crypto_investigator/planner/`,
  `tests/unit/test_planner_v8.py` 與對應 docs。
- Milestone 3：`src/crypto_investigator/application/execution_*`,
  `src/crypto_investigator/services/`,
  `tests/unit/test_execution_v8.py` 與對應 docs。
- Milestone 4：Case result/report/package/import/export services、
  `tests/unit/test_case_output_v8.py`、CLI、README 與 docs。
- Milestone 5～6：`src/crypto_investigator/ui/`, `__main__.py`,
  `pyproject.toml`, `requirements.lock`, UI/integration tests、benchmark、README
  與 UI docs。

Git 可用以下指令精確重建每個版本的檔案清單：

```powershell
git show --stat 73ed66d
git show --stat 9da97a0
git show --stat 5340e40
git show --stat bee9c17
git show --stat 8d7519e
git show --stat 48d3b66
```

## 6. 重要架構決策、限制與安全設計

- **本機優先：** 案件、evidence、artifact、cache、report 均可在本機保存。
- **Domain boundary：** Provider/importer transport model 不能直接成為 Analyzer/
  Graph/AI 的共享模型；先正規化成 Domain Transaction。
- **Deterministic first：** V6.5 facts/observations 不依賴 AI；相同輸入應得到相同
  結果。
- **Epistemic boundary：** confirmed facts、deterministic observations、
  candidate interpretations 必須分開；不得把候選身分或犯罪推論寫成事實。
- **Safe Case ID：** workspace 目錄使用 opaque safe ID，不使用案件名稱。
- **Workspace confinement：** 正式紀錄只存相對路徑，並檢查 traversal/symlink。
- **Evidence immutability：** 匯入後原始 evidence 不可被修改；記錄 SHA-256、
  size、type、timezone-aware timestamp。
- **Atomic persistence：** Case、plan、execution 等正式 JSON 使用 atomic write。
- **Append-only audit：** Audit/event/log 追加寫入，Audit 使用 hash chain。
- **Unknown-field preservation：** case schema migration 不靜默遺失未知欄位。
- **Bounded operations：** Provider pagination、retry、records、package size/
  compression ratio 均有硬限制；timeout 之外的 OpenAI 4xx 不自動 retry。
- **Partial preservation：** 某 Provider、step 或 exporter 失敗時保留已成功結果，
  並明確標記 partial/unavailable，不宣稱完整成功。
- **Secret redaction：** 不保存 API Key、Authorization Header、password、token、
  request body、完整 prompt 或 schema；OpenAI error artifact 只保留安全欄位。
- **Offline HTML：** 報告及 Graph 不依賴外部 CDN，輸入需 escaping，禁止 script/
  event-handler injection。
- **UI allowlist：** UI settings 僅接受非秘密欄位；AI 預設關閉，錯誤畫面不顯示
  traceback 或秘密。
- **Immutable report/package versions：** 報告使用 `reports/vNNN`，package manifest
  使用 canonical SHA-256 inventory。
- **Deidentification irreversible：** alias salt/mapping 不納入 package，原始 evidence
  不納入 deidentified export。

主要 ADR 位於 `docs/decisions.md`；整體結構位於 `docs/architecture.md`。

## 7. UI 與案件流程現況

```text
首頁
 -> 五步驟建立案件 Wizard
 -> 線索與 Evidence
 -> Goals
 -> 產生及確認 deterministic Plan
 -> Execution timeline
 -> Result Dashboard
 -> Investigation / Counterparty / Graph / Narrative
 -> Report
 -> Audit
```

- **首頁：** 建立案件、最近案件、open/running/partial/review 摘要、安全系統狀態。
- **Wizard：** metadata、context、evidence、confirmed clues、goals；未勾選確認的
  地址/Tx Hash 不保存。
- **Evidence：** 經 immutable import service 複製、hash、登錄相對路徑。
- **Planner：** deterministic 產生，顯示 reasons、provider、bounded parameters、
  warnings、dependencies，必須明確確認。
- **Execution：** timeline、stage、records、warning/partial/failed/cancelled；
  總量未知時不顯示假百分比。
- **Result：** scope/completeness、按資產分卡、confirmed/observation/candidate 分離。
- **Graph：** 顯示已存在且位於 workspace 的 `flow.html`。
- **Narrative：** 顯示 fallback/AI/validation/review 狀態；AI disabled by default。
- **Report：** 背景建立 Markdown/HTML/DOCX/PDF，版本保留。
- **Audit：** 人類可讀 timeline，technical metadata 次要顯示，可驗證 hash chain。
- **快捷鍵：** `Ctrl+N` 新案件、`Ctrl+O` 案件清單、`Ctrl+S` 保存、
  `Ctrl+Enter` 下一階段；`Esc` 不取消執行。

## 8. 安裝、啟動、測試與打包指令

### 建立 Python 3.12 環境與安裝

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -e .
python -m pip check
```

如不要求完全重現凍結環境，可只執行：

```powershell
python -m pip install -e .
```

### 啟動

```powershell
python -m crypto_investigator
python -m crypto_investigator ui
python -m crypto_investigator ui --case-root cases
python -m crypto_investigator --help
```

### 測試

```powershell
python -m pytest
python -m pytest -q -rs
python -m pytest tests/ui tests/integration/test_desktop_case_flow_v8.py
```

### Case output/package

```powershell
python -m crypto_investigator case-result <CASE_ID>
python -m crypto_investigator case-report <CASE_ID> --format all
python -m crypto_investigator case-export <CASE_ID> output\case --mode full
python -m crypto_investigator case-package-validate output\case.chainsherlock-case.zip
python -m crypto_investigator case-import output\case.chainsherlock-case.zip
```

目前沒有可確認的 Windows 應用程式 installer/build 指令。不要把 Case package
指令誤認為桌面應用程式打包。

## 9. 測試紀錄

### 先前已知驗收結果（非本輪重跑）

- Python：3.12.13
- pytest：8.4.2
- PySide6：6.11.1
- 完整 suite：1,143 collected；1,142 passed；1 skipped；44.36 秒。
- `pip check`：No broken requirements found.
- V8 M6 UI/integration：204 passed，其中 M6 新增 99 tests。
- skipped 項為需要外部真實 AI 設定的 integration test；離線 suite 不呼叫付費 API。

### 本輪恢復驗收

文件初稿建立後實際執行結果：

- Python：3.12.13
- pytest：8.4.2
- PySide6：6.11.1
- `python -m pip install -e .`：成功，建立並安裝
  `chain-sherlock==0.1.4` editable wheel。
- `python -m pip check`：成功，`No broken requirements found.`
- `python -m pytest -q -rs`：成功，`1142 passed, 1 skipped in 36.07s`。
- 唯一 skip：
  `tests/test_v7_ai_narratives.py:329: real AI key not configured`。
- 沒有測試失敗；本輪未呼叫真實 AI 或付費模型。

第一次 editable install 在 sandbox 內因無法連線取得 isolated build dependency
`hatchling` 而失敗；允許 pip 網路存取後只重試安裝步驟即成功。這是執行環境
網路限制，不是 package dependency conflict；已通過的完整 pytest 沒有重跑。

## 10. Benchmark 紀錄

V8 Milestone 6 在 Windows／Python 3.12.13／PySide6 6.11.1 的既有單次結果：

| 項目 | 結果 |
|---|---:|
| cold startup | 8.823 ms |
| main window | 69.236 ms |
| home render | 105.044 ms |
| wizard open | 4.805 ms |
| 100-case list | 1,000.497 ms |
| case open | 28.398 ms |
| plan render | 0.054 ms |
| execution timeline | 0.084 ms |
| result dashboard | 0.055 ms |
| investigation view | 0.034 ms |
| graph page | 0.022 ms |
| report preview | 1.137 ms |
| 1,000 evidence model | 0.184 ms |
| 10,000 counterparties model | 0.176 ms |
| 10,000 counterparties sort | 8.548 ms |
| traced current memory | 2.846 MB |
| traced peak memory | 3.639 MB |

這些是本機 regression 參考，不是跨硬體效能保證。

## 11. Git 歷史、狀態與差異摘要

### 主要版本 Commit

| 版本 | Commit |
|---|---|
| V1 | `b312d91` |
| V1.1 | `fac958c` |
| Domain Layer | `b93eddd` |
| V2 | `c2e333a` |
| V3 | `aac03ad` |
| V4 | `279e906` |
| V4.2 | `8a11657` |
| V5 | `e8647bf` |
| V6 | `d2849e8`, `70035ab` |
| V6.5 | `18cd61f`, `3561bf4` |
| V7 | `7cc05b3` |
| V7.1 | `111ade0` |
| V7 error diagnostics | `c2db8cb` |
| V7.2 | `ec720ba` |
| Repository artifact cleanup | `b25e54d` |
| V8 M1 | `73ed66d050b26f8cc2cb932644410f9533dbd2b5` |
| V8 M2 | `9da97a0e03fad9f6494dc3b41fb4034047a3e09c` |
| V8 M3 | `5340e4035b8e4141c73d33e78dfc27b0a84d1142` |
| V8 M4 | `bee9c17ab2d0a6421b2fa152c178898d9c5c099a` |
| V8 M5 | `8d7519e281cd3c854ec469d558aed4fd1fb4d7a4` |
| V8 M6 | `48d3b66b55a6838f254003369384233a29c59cf1` |

### 建立本文件前

- `main` 與 `origin/main` 同步於 `48d3b66b55a6838f254003369384233a29c59cf1`。
- 工作樹乾淨，沒有 tracked 或 untracked change。
- 6 個 V8 commits 已於本輪前推送到 GitHub。

### 建立本文件後

- `git status -sb`：

  ```text
  ## main...origin/main
  ?? PROJECT_RECOVERY_CONTEXT.md
  ```

- `main` 仍與 `origin/main` 同步；本輪沒有新 commit。
- 唯一變更是未追蹤的 `PROJECT_RECOVERY_CONTEXT.md`。
- 因檔案尚未加入 Git，`git diff --stat` 與 `git diff` 皆為空；
  `git ls-files --others --exclude-standard` 只列出本文件。
- 本輪未修改既有程式與測試。

## 12. 建議下一步順序

在沒有新的功能批准前，建議依序：

1. 將本恢復文件納入 Git（需要使用者明確要求 commit/push）。
2. 修正 README 的版本/里程碑矛盾，但不要改程式架構。
3. 為 UI 註冊受控的 V2～V7 StepHandler adapters，先做單一 mock/fixture
   端到端驗收，再做真實 Provider；這應是 V8 後續最優先缺口。
4. 補 UI 真實 Provider connection test 與安全錯誤呈現。
5. 補 Graph artifact 產生流程與 UI 間的明確 service boundary；是否做互動聯動
   需另行批准。
6. 完成 Report preview/review/approval 的產品決策與驗收。
7. 最後才規劃 Windows installer、code signing 與 release pipeline。
8. V9、Cross-chain、Risk/AML、商業 API 或 Web UI 必須等待新的明確 Prompt。

## 13. 恢復時的禁止事項

- 不得因本文件而重寫 V2～V7。
- 不得把 AI candidate 或 rule observation 提升為 confirmed fact。
- 不得把不同資產金額相加。
- 不得保存 API Key、Authorization Header、完整 prompt 或來源絕對路徑。
- 不得跳過 Plan confirmation 或 Execution policy。
- 不得在未經批准時開始 V9、Cross-chain、Risk/AML、商業 API、Web UI 或
  Windows installer。

## 14. 恢復後續：V8 Milestone 7

基準文件提交並推送後，V8 Milestone 7 已完成離線 execution integration：

- Desktop UI 預設建立離線 Execution Registry。
- CSV／XLS／XLSX Evidence 接入既有 Importer、Normalizer、Domain、Analysis、
  Investigation、Graph 與 deterministic Case Report。
- structured Evidence 地址 Plan 使用 `case_evidence`，不宣稱或呼叫 Provider。
- 每次執行重新驗證 Evidence SHA-256，artifacts 使用相對路徑、SHA-256 與唯讀
  registration。
- PDF 缺少 CJK 字型時維持既有 partial export policy。
- 驗收：`1147 passed, 1 skipped in 41.01s`；`pip check` 通過。
- 唯一 skip 是未配置真實 AI Key；本 Milestone 未呼叫 Provider 或 AI。

下一個待批准項目是 bounded real Provider StepHandler integration；其後才是
Windows packaging。不得直接開始 V9。

### V8.7.1 PDF 字型修正

- 字型解析順序：明確參數、環境變數、Windows 系統標楷體。
- `export_status.json` 只保存可用狀態、字型名稱與來源類別，不保存本機路徑。
- 不複製或提交 Windows 專有字型；無可用字型時仍採 partial export。
- 完整驗收：`1148 passed, 1 skipped in 37.54s`；`pip check` 通過。

## 15. 恢復後續：V8 Milestone 8

- Desktop hybrid registry 支援 Provider-only address/transaction Plan。
- structured Evidence 仍優先走 M7 離線 handler，不會意外呼叫 Provider。
- Etherscan/Blockscout、TronGrid、Blockstream 結果接入 Analysis、Graph 與
  deterministic Investigation。
- 下游 steps 讀取已驗證 AnalysisResult artifact，不重複發出 Provider 請求。
- provider status、errors、rejected records 再經 redaction 後以相對路徑與
  SHA-256 登錄。
- M8-A 最終完整驗收：`1150 passed, 1 skipped in 43.51s`；`pip check` 通過。
- M8-B 三鏈單頁／20 筆／0 retry 真實驗收均完成，皆因 bounded truncation 或
  capability 缺口正確標記 partial，但 Graph/Investigation 完成且 0 fatal failure。
- 秘密與本機絕對路徑掃描命中 0；raw 驗收 artifacts 位於 ignored `output/`。
