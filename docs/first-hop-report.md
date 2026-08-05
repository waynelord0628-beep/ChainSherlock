# Address Profile and First-Hop Fund Flow Analysis

ChainSherlock 的第一層報告直接由案件 Goal、Evidence、Provider 結果、正規化交易、
Local Labels 與完整度 metadata 產生。它不需要外部參考報告，也不把 AI 當成數值、
排名、資產角色或標籤的決策來源。

## Product contract

案件 Goal 明確保存 required assets、required capabilities、scope、各資產
materiality threshold、output type 與 completeness requirement。正式流程將同一案件
中的 Provider 與本地 Evidence 合併為同一分析母體，不因來源檔案數量拆成多份報告。

資產依下列角色排序：

1. `principal_value_asset`
2. `secondary_value_asset`
3. `operational_asset`
4. `spam_or_low_materiality_asset`
5. `unknown_or_non_value_event`

不同資產的金額永不相加。零值互動保留於紀錄，但不計入資產金額。當缺少跨資產估值
依據時，案件 Goal 的 required assets 優先於名目數量；報告須揭露此限制。

## Deterministic narrative

執行摘要只組裝已存在的 structured facts，回答主要價值資產、流入／流出、雙向總量、
淨流量、來源／去向集中度、第一層優先地址、完整度與證據邊界。沒有資料支持的句子及
空表不會輸出。

第一層追查候選的 priority 只表示下一步查詢順序，不代表風險、身分、下車點或最終
受益人已確認。相鄰流入後流出只代表時間接近，不是逐筆資金同一性證明。

## Labels and follow-up

Label 必須保存 chain、address、label、category、source、reference、confidence、
verification status、imported_at 與 notes。衝突時採人工確認、可信 Local Label、
Provider label、未驗證候選的順序；未匹配地址保持未標記。

後續任務由本案候選與缺口生成，保存所需資料、預期回答、Evidence refs 與停止條件。
第二層追蹤不在 V8 First-Hop productization 範圍內。

## Artifacts

正式服務可輸出 `first_hop_product.json`、`first_hop_candidates.csv`、四格式報告及
deterministic SVG 圖表。圖表與表格共用同一 structured source，保存 SHA-256，
不載入外部 URL。
