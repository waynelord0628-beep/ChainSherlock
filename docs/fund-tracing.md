# Evidence-based Fund Tracing and Off-ramp Workflow

## 1. 目前產品邊界

ChainSherlock V8 現有正式報告定位為：

> 地址剖繪與第一層資金流分析報告
>
> Address Profile and First-Hop Fund Flow Analysis

目前能力會分析目標地址本身，並列出第一層主要來源、主要去向、高頻交易對手、
行為模式及規則式觀察。它尚未：

- 對所有主要去向取得下一層交易；
- 建立 transaction-level path tracing；
- 驗證跨多筆交易的資金配置關係；
- 確認最終下車點、實際受益人或控制人。

來源排行與去向排行只能並列為候選摘要，不得拼接成已確認資金路徑。

## 2. Evidence Gate

多層追蹤只能建立在已驗證的交易 artifact 上。每條 Trace Edge 必須具有真實
transaction hash、資產、金額、時間與 Evidence references。Provider 不完整、
交易不存在、資產不一致或 Evidence 無法驗證時，該 Edge 不得進入正式路徑。

不同資產不得合併成同一條金額路徑；如需估值，必須另建有時間點與價格來源的
valuation layer，不得修改原始資產數值。

## 3. Seed

支援的 Seed：

- address
- transaction hash
- victim transfer
- selected outgoing transaction

Seed 至少保存 type、value、chain、asset（如適用）與 Evidence references。

## 4. Trace Node

Trace Node 至少包含：

- chain
- address
- transaction
- asset
- amount
- timestamp
- hop
- role
- label status
- evidence refs

Role 與 Label 必須區分 confirmed、candidate、unlabeled 與 manual review。

## 5. Trace Edge

Trace Edge 至少包含：

- from
- to
- transaction hash
- asset
- amount
- timestamp
- allocation method
- confidence
- evidence refs

允許的 allocation method 包括 direct transaction、FIFO、proportional 與 manual。
除 direct transaction 外，配置方法屬分析模型，不得被描述成鏈上直接事實。

## 6. Trace Scope

每次追蹤必須明確保存：

- full history／custom period
- max depth
- max nodes
- max records
- minimum material amount
- asset filters
- date range
- timezone
- required capability completeness

任何安全上限被觸發時必須標記 partial，不得宣稱完整多層追蹤。

## 7. Stop Conditions

可序列化的停止條件：

- confirmed exchange／VASP
- payment service
- OTC candidate
- mixer
- bridge
- no further outgoing activity
- below materiality threshold
- max depth reached
- provider incomplete
- manual stop

停止原因、觸發層級與 Evidence 必須保留。Candidate 類型停止條件不等於身分已確認。

## 8. 第一層追查優先順序

第一層主要去向採 deterministic priority：

1. received amount descending
2. interaction count descending
3. rapid onward transfer
4. aggregation behavior
5. known or candidate VASP label
6. materiality
7. completeness

排序只決定下一個查詢目標，不代表風險或犯罪程度。低於 materiality threshold 的
4 TRX、8 TRX 等小額地址，不得與數千 TRX 的主要去向同等優先。

本次 TRON fixture 的優先候選至少包括地址-003、地址-013及其他具有實質金額的
第一層去向；真正展開前仍須重新驗證地址 mapping、Scope 與 Provider completeness。

## 9. Off-ramp Candidate

Off-ramp Candidate 至少保存：

- address
- label
- label source
- received amount
- transaction count
- first／last receipt
- subsequent behavior
- confidence
- evidence
- recommended legal／investigative action
- limitations

只有可信 Label 與交易 Evidence 支持時，才能使用「已確認 VASP」等較強語意。
其他情況必須維持「候選」並提供人工覆核入口。

## 10. 未來正式報告結構

1. 調查目的與 Seed
2. 關鍵地址對照表
3. 資產與追蹤範圍
4. 第一層資金流
5. 第二層資金流
6. 後續層級
7. 分流與合流
8. 主要資金路徑
9. 已確認 VASP／服務商
10. 下車點候選
11. 調閱／凍結／扣押建議
12. 未解決路徑
13. 完整度與限制
14. Evidence Index
15. 技術附錄

「主要資金路徑」中的每一條 Edge 都必須由真實交易支持。不得使用最大來源與
最大去向排行組合代替 transaction-level tracing。

## 11. 本階段不包含

- 不呼叫 Provider 或 AI；
- 不展開第二層地址；
- 不產生下車點結果；
- 不建立犯罪、洗錢或詐欺判斷；
- 不開始 V9 或 Windows 打包。
