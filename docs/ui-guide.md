# ChainSherlock Desktop UI Guide

## Crypto Investigation Command Center

V8 pre-packaging redesign 使用深石墨藍黑介面、低飽和青綠主操作與冷藍／紫／
琥珀狀態色。所有狀態仍同時顯示文字，不以顏色取代語意。首頁 Hero 的節點連線
是明確的靜態裝飾，不代表任何案件地址、交易或金額。

首頁包含：

- `CRYPTO INVESTIGATION COMMAND CENTER` 與 local-first／evidence-based 標示。
- Operational Cards：進行中案件、執行中的工作、部分完成、等待審核。
- Investigation Queue：只呈現已保存案件摘要；無案件時提供建立／開啟操作。
- System Readiness：只檢查安全的本機設定存在性，不主動呼叫 Provider。
- LIVE EXECUTION：未知總量採 indeterminate progress，不產生推測百分比。

案件工作區依序為：案情、線索、Evidence、調查目標、調查計畫、Execution、
Result、Investigation、Counterparty、Graph、Narrative、Report、Review、Audit。
地址、Tx Hash、SHA-256 預設縮寫並使用 monospace；完整值保留於可選取／複製
的安全呈現，不在裝飾區建立假資料。

Graph 仍只允許案件 workspace 內既有 `flow.html`，不載入外部 URL。PDF CJK
Font readiness 只顯示字型名稱與來源類別，不顯示本機絕對路徑。

## Milestone 6 workflow

首頁的「建立新案件」會開啟五步驟 Wizard：

1. 基本資料：標題、案件編號、主要鏈、負責人與 tags。
2. 案件說明：案件背景與待回答問題。
3. 匯入證據：選擇原始檔，建立案件後計算 SHA-256。
4. 確認線索：地址、Tx Hash、資產與金額；未勾選確認就不會保存。
5. 調查目標：選擇本案要回答的問題。

開啟案件後，左側 workflow 依序顯示案件總覽、線索與證據、調查目標、調查
計畫、執行進度、結果總覽、Investigation、交易對手、Graph、Narrative、
報告與稽核紀錄。頁首會顯示目前階段和下一個可執行動作。

Plan 使用人類可讀 step cards；advanced limits 只顯示必要 bounded parameters。
Execution 使用 timeline，總量未知時只顯示 records 與 stage。Result Dashboard
將資產分卡呈現，Confirmed、Observation 與 Candidate 永遠分開。

鍵盤操作：`Ctrl+N` 建立案件、`Ctrl+O` 開啟案件清單、`Ctrl+S` 儲存案件、
`Ctrl+Enter` 前往下一個 workflow stage。`Esc` 不會取消正在執行的案件。

## 啟動

```powershell
python -m crypto_investigator
python -m crypto_investigator ui --case-root cases
```

## 案件流程

1. 在「建立案件」輸入標題，可選填主要鏈、地址與 Tx Hash。
2. 進入案件工作區後，在「證據」匯入 CSV、Excel、JSON、PDF 或文字證據。
3. 在「調查目標」確認已保存的 Goals。
4. 在「調查計畫」背景產生 deterministic Plan，檢查 bounded parameters、
   warnings、optional steps 與 dependencies，再明確確認 Plan。
5. 「執行進度」呈現目前 stage、records、warnings、partial、failed 或 cancelled；
   未知總量顯示 indeterminate progress，不推測百分比。
6. 「分析結果」與「Investigation」分開呈現 confirmed facts、deterministic
   observations、candidate interpretations、unresolved questions 與 recommendations。
7. 「Graph」只載入案件內既有 `flow.html`，不在 UI 重新產生 Graph。
8. 「Narrative」揭露 AI／fallback／validation／review 狀態；AI 預設關閉。
9. 「報告」可在背景產生 Markdown、HTML、DOCX、PDF，並保留所有版本。
10. 「Audit Log」顯示 action 與 hash-chain integrity。

## Cancellation 與 Resume

背景 worker 支援 cooperative cancellation。Execution 的取消、resume 與 retry
由既有 `CaseExecutionService` gate 決定；已完成 step 不會重跑。UI 不會繞過
未確認 Plan、terminal execution 或 unsupported handler 的限制。

## Partial 與候選資訊

`partial`、`warning`、`failed`、`cancelled` 均以明確文字與視覺狀態呈現。
Candidate 不會顯示為 Confirmed；AI 或規則推論也不會被提升為已確認事實。

## Settings 與安全

UI 設定只保存 theme、language、timezone、case root、視窗狀態、bounded
Provider limits 與非秘密 AI 選項。API Key、Authorization Header、Password、
Token、完整 Prompt 與 Secrets 不會寫入設定檔、畫面 log 或錯誤訊息。

錯誤畫面只顯示安全訊息、stage 與建議操作，不顯示 traceback。Evidence 與
artifact 路徑必須位於案件 workspace；Graph 亦只接受其中的 `flow.html`。

## M5 Benchmark

Windows、Python 3.12.13、PySide6 6.11.1 的 offscreen 驗收結果：

- cold startup：7.388 ms
- main window render：28.856 ms
- 100 cases list/load：1,077.122 ms
- case open：22.628 ms
- 1,000 evidence model：0.112 ms
- 10,000 counterparty model：0.101 ms
- 10,000 counterparty sort：4.526 ms
- Python traced peak memory：3.222 MB

數值為本機單次基準，僅供 regression 比較，不代表不同硬體的效能保證。

## M6 Benchmark

- cold startup：8.823 ms
- main window：69.236 ms
- home render：105.044 ms
- wizard open：4.805 ms
- 100-case list：1,000.497 ms
- case open：28.398 ms
- plan render：0.054 ms
- execution timeline：0.084 ms
- result dashboard：0.055 ms
- investigation view：0.034 ms
- graph page：0.022 ms
- report preview：1.137 ms
- 10,000 counterparty sort：8.548 ms
- Python traced peak memory：3.639 MB
