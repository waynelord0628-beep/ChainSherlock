# ChainSherlock Desktop UI Guide

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
