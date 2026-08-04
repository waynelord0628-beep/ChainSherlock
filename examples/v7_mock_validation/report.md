# ChainSherlock 區塊鏈幣流分析報告

- 報告編號：CSR-E4F1CFE7E8A9
- 產生時間：2026-08-04T08:18:01.188968+00:00
- Chain：ethereum
- 目標：0x1111111111111111111111111111111111111111
- 資料完整度：complete
- 交易筆數：10


## 封面

ChainSherlock




## 執行摘要

共分析 10 筆交易。

資料完整度：complete。




## 資料完整度

分析完整度：complete。

Provider 錯誤：0 筆。

被拒絕資料：0 筆。




## 資料來源

證據檔案數：12。




## 分析標的

標的：0x1111111111111111111111111111111111111111

鏈別：ethereum




## 分析摘要



### 摘要指標

| 指標 | 值 |
| --- | --- |

| first_seen | 2026-01-01T00:00:00+00:00 |

| last_seen | 2026-10-10T09:00:00+00:00 |

| transaction_count | 10 |

| incoming_count | 5 |

| outgoing_count | 5 |

| unique_counterparties | 1 |

| active_days | 10 |

| unconfirmed_count | 0 |

| missing_timestamp_count | 0 |




## 資產流向



### 依資產分離之流入／流出

| 資產 | 流入 | 流出 |
| --- | --- | --- |

| ETH | 18.5 | 17.5 |

| USDT | 9.0 | 15.0 |




## 主要交易對手



### Top 20 Counterparties

| address | incoming_count | outgoing_count | interaction_count | first_seen | last_seen | direction |
| --- | --- | --- | --- | --- | --- | --- |

| 0x2222222222222222222222222222222222222222 | 5 | 5 | 10 | 2026-01-01T00:00:00+00:00 | 2026-10-10T09:00:00+00:00 | unknown |




## 時間軸

每日區間數：10；每月區間數：10。




## 交易關係圖

節點：2；邊：4；截斷：False。




## 調查特徵

本節為 deterministic rule engine 結果，不使用 AI、風險分數或身分推論。

資料完整度：complete。




## 方向對帳

failed transaction 另行排除；目前數量列於表中。



### 方向對帳

| 指標 | 值 |
| --- | --- |

| transaction_count | 10 |

| incoming_count | 5 |

| outgoing_count | 5 |

| self_transfer_count | 0 |

| neutral_count | 0 |

| unclassified_direction_count | 0 |

| failed_transaction_count | 0 |

| duplicate_removed_count | 0 |

| reconciled | True |




## 各資產供款來源



### 各資產前十大供款來源

| 排名 | 資產 | 地址 | 金額 | 占比 | 首次 | 最後 |
| --- | --- | --- | --- | --- | --- | --- |

| 1 | ETH | 0x2222222222222222222222222222222222222222 | 18.5 | 1 | 2026-01-01T00:00:00+00:00 | 2026-09-09T08:00:00+00:00 |

| 1 | USDT | 0x2222222222222222222222222222222222222222 | 9.0 | 1 | 2026-01-01T00:00:00+00:00 | 2026-09-09T08:00:00+00:00 |



### 供款來源變化

|
|




## 客觀觀察

本節僅描述資料中的可驗證模式，不進行犯罪、風險或身分推論。




## 資料限制

本報告不提供 AML、犯罪、風險或法律判定。

未知地址未進行 KYC、IP、地理位置或實體身分推論。




## 主要資金去向與角色候選

無 Local Label 時，service／exchange／payment／OTC 僅表示規則候選。



### 主要交易對手橫向摘要

| 排名 | 地址 | 標籤 | 候選角色 | 方向 | 交易次數 | 資產 | 流入金額 | 流出金額 | 占比 | 首次 | 最後 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

| 1 | 0x2222222222222222222222222222222222222222 |  | unknown candidate | outgoing | 10 | ETH | 18.5 | 17.5 | 1 | 2026-01-01T00:00:00+00:00 | 2026-10-10T09:00:00+00:00 |

| 1 | 0x2222222222222222222222222222222222222222 |  | unknown candidate | outgoing | 10 | USDT | 9.0 | 15.0 | 1 | 2026-01-01T00:00:00+00:00 | 2026-10-10T09:00:00+00:00 |




## 運作階段



### Operation Stages

| 階段 | 開始 | 結束 | 交易數 | 資產 | 主要來源 | 主要去向 | 原因 | 可信度 | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

| dormant | 2026-01-01T00:00:00+00:00 | 2026-02-02T01:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| startup | 2026-01-01T00:00:00+00:00 | 2026-02-02T01:00:00+00:00 | 2 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['first_sample_window'] | medium | ['IF0'] |

| recovery | 2026-02-02T01:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 9 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dominant | 2026-03-03T02:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 8 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['funding_concentration_threshold'] | medium | ['IF0'] |

| dormant | 2026-03-03T02:00:00+00:00 | 2026-04-04T03:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| dormant | 2026-04-04T03:00:00+00:00 | 2026-05-05T04:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-04-04T03:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 7 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dormant | 2026-05-05T04:00:00+00:00 | 2026-06-06T05:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-05-05T04:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 6 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dormant | 2026-06-06T05:00:00+00:00 | 2026-07-07T06:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-06-06T05:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 5 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dormant | 2026-07-07T06:00:00+00:00 | 2026-08-08T07:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-07-07T06:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 4 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dormant | 2026-08-08T07:00:00+00:00 | 2026-09-09T08:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-08-08T07:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 3 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| dormant | 2026-09-09T08:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 0 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['transaction_gap_exceeds_threshold'] | medium | ['IF0'] |

| recovery | 2026-09-09T08:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 2 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |

| recovery | 2026-10-10T09:00:00+00:00 | 2026-10-10T09:00:00+00:00 | 1 | ['ETH', 'USDT'] | ['0x2222222222222222222222222222222222222222'] | ['0x2222222222222222222222222222222222222222'] | ['activity_after_dormancy'] | medium | ['IF0'] |




## 休眠與重新啟用

partial 資料可能影響交易間隔；本報告不把資料邊界本身視為休眠證據。

目前偵測區間數：8。



### 休眠區間

| behavior_changed | dormant_days | ended_at | post_recovery_average_amount_by_asset | post_recovery_daily_frequency | reactivated | started_at |
| --- | --- | --- | --- | --- | --- | --- |

| False | 32 | 2026-02-02T01:00:00+00:00 | {'ETH': '3.0'} | 0.06666666666666666666666666667 | True | 2026-01-01T00:00:00+00:00 |

| False | 32 | 2026-04-04T03:00:00+00:00 | {'USDT': '4.5'} | 0.03333333333333333333333333333 | True | 2026-03-03T02:00:00+00:00 |

| False | 31 | 2026-05-05T04:00:00+00:00 | {'ETH': '5.5'} | 0.03333333333333333333333333333 | True | 2026-04-04T03:00:00+00:00 |

| False | 32 | 2026-06-06T05:00:00+00:00 | {'ETH': '6.5'} | 0.03333333333333333333333333333 | True | 2026-05-05T04:00:00+00:00 |

| False | 31 | 2026-07-07T06:00:00+00:00 | {'USDT': '7.5'} | 0.03333333333333333333333333333 | True | 2026-06-06T05:00:00+00:00 |

| False | 32 | 2026-08-08T07:00:00+00:00 | {'ETH': '8.5'} | 0.03333333333333333333333333333 | True | 2026-07-07T06:00:00+00:00 |

| False | 32 | 2026-09-09T08:00:00+00:00 | {'ETH': '9.5'} | 0.03333333333333333333333333333 | True | 2026-08-08T07:00:00+00:00 |

| False | 31 | 2026-10-10T09:00:00+00:00 | {'USDT': '10.5'} | 0.03333333333333333333333333333 | True | 2026-09-09T08:00:00+00:00 |




## 資金停留時間

採 FIFO approximation、不得解讀為實際同一筆資金流向，且不跨資產配對。



### 依資產分離之 FIFO 統計

| 資產 | 配對流入 | 配對流出 | 未配對流入 | 未配對流出 | 平均秒數 | 中位秒數 | 5 分鐘內 | 1 小時內 | 24 小時內 | 事件數 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

| ETH | 9.0 | 9.0 | 9.5 | 8.5 | 6402000.0 | 8218800.0 | 0 | 0 | 0 | 3 |

| USDT | 9.0 | 9.0 | 0 | 6.0 | 8132400.0 | 8132400.0 | 0 | 0 | 0 | 2 |




## 轉帳模式

門檻來自 settings snapshot；dust TRX 不列為重要固定金額模式。



### 模式摘要

| 指標 | 值 |
| --- | --- |

| fixed_amounts | {'ETH': [], 'USDT': []} |

| integer_amount_ratio | 0 |

| amount_suffix_counts | {'5': 10} |

| batch_outgoing_count | 0 |

| batch_incoming_count | 0 |




## 客觀觀察



### Deterministic Observations

| 代碼 | 事實敘述 | 數值 | 原因 | Evidence | 可信度 | 限制 |
| --- | --- | --- | --- | --- | --- | --- |

| dormant_reactivation | 目前樣本顯示連續 32 天沒有交易，之後出現交易。 | {'dormant_days': 32} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 32 天沒有交易，之後出現交易。 | {'dormant_days': 32} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 31 天沒有交易，之後出現交易。 | {'dormant_days': 31} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 32 天沒有交易，之後出現交易。 | {'dormant_days': 32} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 31 天沒有交易，之後出現交易。 | {'dormant_days': 31} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 32 天沒有交易，之後出現交易。 | {'dormant_days': 32} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 32 天沒有交易，之後出現交易。 | {'dormant_days': 32} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |

| dormant_reactivation | 目前樣本顯示連續 31 天沒有交易，之後出現交易。 | {'dormant_days': 31} | ['transaction_gap_exceeds_threshold'] | ['IF0'] | medium | [] |




## Conclusion Facts



### 結論事實

| Fact | 值 | 單位 | 可信度 | 原因 | Evidence | 限制 |
| --- | --- | --- | --- | --- | --- | --- |

| dominant_funder_exists | True | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| dominant_funder_address | {'ETH': '0x2222222222222222222222222222222222222222', 'USDT': '0x2222222222222222222222222222222222222222'} | address_by_asset | high | ['deterministic_rule'] | ['IF0'] | [] |

| dominant_funder_share_by_asset | {'ETH': '1', 'USDT': '1'} | ratio_by_asset | high | ['deterministic_rule'] | ['IF0'] | [] |

| funding_source_changed | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| funding_transition_count | 0 | count | high | ['deterministic_rule'] | ['IF0'] | [] |

| dormant_period_detected | True | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| longest_dormant_days | 32 | days | high | ['deterministic_rule'] | ['IF0'] | [] |

| reactivation_detected | True | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| batch_incoming_detected | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| batch_outgoing_detected | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| fixed_amount_pattern_detected | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| rapid_pass_through_detected | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| service_candidate_count | 0 | count | high | ['deterministic_rule'] | ['IF0'] | [] |

| graph_truncated | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| provider_truncated | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| analysis_partial | False | — | high | ['deterministic_rule'] | ['IF0'] | [] |

| unknown_direction_count | 0 | count | high | ['deterministic_rule'] | ['IF0'] | [] |




## AI 輔助敘事：調查摘要

AI 輔助敘事；provider=deterministic-fallback；model=template-v1；prompt=7.0.0；validation=passed；fallback=True。 AI 內容尚未經人工確認。

分析期間為 2026-01-01T00:00:00+00:00 至 2026-10-10T09:00:00+00:00，結構化樣本共 10 筆，完整度為 complete。本段僅整理 V6.5 已驗證事實，不作犯罪、身分或風險判定。




## AI 輔助敘事：資金來源分析

目前樣本的主要供款來源候選為 0x2222222222222222222222222222222222222222，排名 1；不代表主控方。




## AI 輔助敘事：資金去向分析

僅依目前結構化去向排行描述；若無資料，無法判定主要流出去向。




## AI 輔助敘事：運作階段

既有 Investigation Engine 共辨識 18 個運作階段；未新增任何階段。




## AI 輔助敘事：批次及固定金額模式

結構化結果包含 0 個模式項目，單次事件不據此擴大解讀。




## AI 輔助敘事：替代解釋

可能為營運型結算、代付、資金調度或未知服務型用途；目前資料尚不能排除其他解釋。




## AI 輔助敘事：後續調查建議

可依現有證據補充本地標籤、提高資料取得上限，並查核主要供款與出金對象；本系統不自動執行。




## AI 輔助敘事：綜合結論

分析期間為 2026-01-01T00:00:00+00:00 至 2026-10-10T09:00:00+00:00，結構化樣本共 10 筆，完整度為 complete。本段僅整理 V6.5 已驗證事實，不作犯罪、身分或風險判定。 所有候選角色與替代解釋均保留不確定語意。




## 結論

本次分析期間為 2026-01-01T00:00:00+00:00 至 2026-10-10T09:00:00+00:00，共納入 10 筆可供 Investigation 使用的交易邊，資料狀態為 complete，涉及資產：ETH, USDT。目前樣本的 funding concentration 為 {'ETH': '1', 'USDT': '1'}；來源切換 0 次；休眠區間 8 個；batch incoming/outgoing 為 0/0；固定金額模式為 False；一小時內 FIFO 配對比例非零為 True。以上只描述目前樣本；Local Label 與 Provider 缺漏可能改變排行與模式。僅依鏈上資料無法判定實際控制人、交易目的或犯罪意圖。




## Evidence Index

[E1] small.csv — 9d0812b2e88940d115c6a02c67dfd7c1ca847959b1693f576982532d72d137c8

[E2] ai_errors.json — 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

[E3] ai_status.json — c069bb2c01d3eab80e2fd314906fa0c7ee70cf37007d5d57f4307e384551584f

[E4] ai_usage.json — 92624426c0f908bff5a21f446df0900575bc39a2ca4212eb6e02a2c5aabc72e9

[E5] analysis.json — d67bf0374c5bce4d966f7a3f0f251d48238a2083c2e9e52cf408aef8d6dd97a6

[E6] flow_graph.json — 041186b0d56a03c717c1e807183f9bfc898f7baecdac4669441316011ea302ce

[E7] narrative.json — b1374c232fe4d747650b4353a82c13bc0b302dcf29ca52cef253417bddd0f546

[E8] narrative_input.json — 11394c208e6e5844e06d18ee98f9e9ad572842426a01f65451e1b3a16a25642c

[E9] narrative_validation.json — 6d3d8fc341c991dcb23131e3318d038c5b6a1be62de8597dcc5e873b1818c52d

[E10] prompt_manifest.json — 3dae860a87f9f86ed6b4fa688f40e248627b3cefdb39cbf6cd19509b872d47c9

[IF0] investigation_evidence.json — hash unavailable

[IF1] investigation_evidence.json — hash unavailable




## 附錄

完整結構化資料請參閱 report_data.json。






## 引用

[E1] small.csv — SHA-256: 9d0812b2e88940d115c6a02c67dfd7c1ca847959b1693f576982532d72d137c8
[E2] ai_errors.json — SHA-256: 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
[E3] ai_status.json — SHA-256: c069bb2c01d3eab80e2fd314906fa0c7ee70cf37007d5d57f4307e384551584f
[E4] ai_usage.json — SHA-256: 92624426c0f908bff5a21f446df0900575bc39a2ca4212eb6e02a2c5aabc72e9
[E5] analysis.json — SHA-256: d67bf0374c5bce4d966f7a3f0f251d48238a2083c2e9e52cf408aef8d6dd97a6
[E6] flow_graph.json — SHA-256: 041186b0d56a03c717c1e807183f9bfc898f7baecdac4669441316011ea302ce
[E7] narrative.json — SHA-256: b1374c232fe4d747650b4353a82c13bc0b302dcf29ca52cef253417bddd0f546
[E8] narrative_input.json — SHA-256: 11394c208e6e5844e06d18ee98f9e9ad572842426a01f65451e1b3a16a25642c
[E9] narrative_validation.json — SHA-256: 6d3d8fc341c991dcb23131e3318d038c5b6a1be62de8597dcc5e873b1818c52d
[E10] prompt_manifest.json — SHA-256: 3dae860a87f9f86ed6b4fa688f40e248627b3cefdb39cbf6cd19509b872d47c9
[IF0] investigation_evidence.json — SHA-256: None
[IF1] investigation_evidence.json — SHA-256: None

