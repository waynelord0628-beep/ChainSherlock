# ChainSherlock 區塊鏈幣流分析報告

- 報告編號：CSR-6CF412C23F75
- 產生時間：2026-08-04T07:39:20.668830+00:00
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

證據檔案數：3。




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

本節為 deterministic rule engine 結果，不使用 AI 或自然語言推理。



### 行為摘要

| 指標 | 值 |
| --- | --- |

| funding_pattern | concentrated |

| distribution_pattern | forwarding |

| frequency | 1.0 |

| counterparty_pattern | concentrated |

| activity_pattern | intermittent |

| operation_stages | ['dormant', 'startup', 'recovery', 'dominant', 'dormant', 'dormant', 'recovery', 'dormant', 'recovery', 'dormant', 'recovery', 'dormant', 'recovery', 'dormant', 'recovery', 'dormant', 'recovery', 'recovery'] |

| dormant | True |

| recovery | True |



### Conclusion Facts

| 指標 | 值 |
| --- | --- |

| funding_source_changed | False |

| dormant_days | 32 |

| main_counterparty_ratio | 1 |

| top_provider_changed | False |

| batch_distribution | False |

| funding_concentration | 1 |

| reactivated | True |




## 客觀觀察

本節僅描述資料中的可驗證模式，不進行犯罪、風險或身分推論。




## 資料限制

本報告不提供 AML、犯罪、風險或法律判定。

未知地址未進行 KYC、IP、地理位置或實體身分推論。




## 結論

本報告已依目前取得的完整資料產生；內容僅為交易資料的描述性整理，不代表犯罪、風險或身分判定。




## Evidence Index

[E1] small.csv — 9d0812b2e88940d115c6a02c67dfd7c1ca847959b1693f576982532d72d137c8

[E2] analysis.json — d67bf0374c5bce4d966f7a3f0f251d48238a2083c2e9e52cf408aef8d6dd97a6

[E3] flow_graph.json — a6e5918fa5b270fa99d5e64467905d7453226e354f2d095e5d6fd933c189bebc




## 附錄

完整結構化資料請參閱 report_data.json。






## 引用

[E1] small.csv — SHA-256: 9d0812b2e88940d115c6a02c67dfd7c1ca847959b1693f576982532d72d137c8
[E2] analysis.json — SHA-256: d67bf0374c5bce4d966f7a3f0f251d48238a2083c2e9e52cf408aef8d6dd97a6
[E3] flow_graph.json — SHA-256: a6e5918fa5b270fa99d5e64467905d7453226e354f2d095e5d6fd933c189bebc

