# Evidence-based Fund Tracing and Off-ramp Workflow

## 目前產品邊界

目前正式報告仍是「地址剖繪與第一層資金流分析報告」。多層追蹤不得以來源、
去向排名拼接成路徑；每條 Trace Edge 必須有真實交易雜湊與 Evidence。

## 標準調查設定

- 預設同時向前及向後追蹤，標準深度 3 層，可由調查人員提高至 5 層。
- USDT、TRX 與其他資產各自追蹤，禁止跨資產加總或 FIFO 配對。
- FIFO 是預設的分析配對方法，不代表識別出鏈上「同一筆」資金。
- 每層套用重要性門檻、節點與紀錄安全上限；觸發上限即標記 partial。
- Provider 未完整取得時保存 checkpoint，後續由游標續跑，不冒充完整結果。

## 資料契約

### Seed

支援地址、交易雜湊、被害人匯款及指定流出交易。Seed 保存 chain、asset 與
Evidence references。

### Trace Node 與 Edge

Node 保存 chain、address、asset、amount、timestamp、hop、role、label status
及 Evidence。Edge 額外保存 from、to、真實 tx hash、allocation method 與
confidence。沒有 tx hash 或 Evidence 的關係不得成為正式 Edge。

### FIFO Lot 與 Allocation

流入交易建立 Fund Lot；流出依時間先後消耗相同資產的可用 Lot。
Allocation Slice 是可重算的分析結果，原始 Edge 永遠保留。不得跨資產、
不得使用晚於流出時間的 Lot，也不得分配超過原始流入金額。

### Checkpoint

Checkpoint 保存 frontier、已訪地址、已訪交易、Provider cursor 與已完成
Edge，不保存 API Key、Authorization Header 或完整 Provider response。

## 關聯與回流

規則式引擎後續至少辨識：

- return flow：資金在後續層回到 Seed 或已訪地址；
- cyclic flow：形成可驗證的交易循環；
- shared counterparty：多條路徑出現共同來源或共同去向；
- aggregation：多個來源在短期間集中至少數節點；
- dispersion：單一或少數節點向多個地址分散；
- revenue-share candidate：固定受款群、比例或週期重複，但只可稱候選。

每個 finding 必須保存資產、hop、地址參照、量化 metrics、reason codes、
confidence、Evidence 與限制。

## 集中後分散的檢查順序

1. 確認集中與分散均由真實交易 Edge 支持。
2. 比較分散地址數、金額占比、時間窗口與重複週期。
3. 檢查固定受款地址、固定比例、固定金額及共同標籤。
4. 區分一次性分流、營運付款與重複分潤候選。
5. 只有人工或可信 Label 能提高身分類語意；規律本身不能確認控制關係。

## 下車點與停止條件

停止條件包括已確認交易所／VASP、支付服務、OTC 候選、Mixer、Bridge、
無後續流出、低於重要性門檻、達最大深度、Provider 不完整及人工停止。

Off-ramp Candidate 必須保存完整地址、Label 與來源、收款金額及次數、
首次／最後收款、後續行為、confidence、Evidence、限制與建議行動。
沒有可信 Label 時只能標示候選，不能確認為交易所或最終受益人。

## 調查優先級

1. 金額較高且資料完整的路徑。
2. 快速後續轉出、集中或突然分散的節點。
3. 多路徑共同對手及回流節點。
4. 已知或候選 VASP／服務商 Label。
5. 重複比例、週期或固定受款群的分潤候選。
6. 低重要性與 dust 資料保留於 Evidence，但預設不占用主要追蹤資源。

## 預計交付順序

1. M1：公開資料契約、FIFO 配對與 checkpoint（離線）。
2. M2：3–5 層雙向 frontier 執行器、去重、取消及續跑。
3. M3：回流、共同對手、集中轉分散及分潤候選規則。
4. M4：Label 驗證、下車點候選與停止條件。
5. M5：合成案例回歸測試及 bounded Provider 驗收。
6. M6：多層追蹤報告與 Graph；AI 僅協助敘事，不建立交易路徑。
