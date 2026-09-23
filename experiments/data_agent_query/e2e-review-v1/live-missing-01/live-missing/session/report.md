# Data Agent 执行结果

请查询 Google Cloud 2022 年营业利润率，返回收入、营业利润和计算依据。仅使用本次选定的冻结资料范围；若所需数据缺失，请明确说明具体缺口，不要用其他年度替代。

状态：**limited**；停止原因：no\_progress\_limit。

计划请求 1 次；执行决策 3 次；工具执行 3 次。

这里展示实际取证结果；取证条件满足不代表业务/风险分析已经完成，候选数据也未被自动采纳。

## 自动生成的任务

| 任务 | 信息要求 | 取证方式 |
| --- | --- | --- |
| google-cloud-2022-operating-margin | Google Cloud 2022 年营业利润率，包括收入、营业利润和计算依据。 | query |

## 实际数字

本轮没有返回数值记录。

## 阅读覆盖与缺口

本轮未设置章节全文阅读要求；数字出处不等于整章已读。

- google-cloud-2022-records-and-margin：google-cloud / revenue / 2022-01-01 — 2022-12-31：尚未取得无冲突的匹配记录。
- google-cloud-2022-records-and-margin：google-cloud / operating\_income / 2022-01-01 — 2022-12-31：尚未取得无冲突的匹配记录。
- google-cloud-2022-records-and-margin：operating\_margin 缺少成功计算或完整、匹配的输入记录。

[查看本次取得的完整原文与来源](report-source-text.md)

## 实际动作

| 轮 | 动作 | 反馈 | 正文累计覆盖 |
| --- | --- | --- | --- |
| 1 | query | recorded | — |
| 2 | search\_source | error | — |
| 3 | query | recorded | — |

## 实际 SQL（DuckDB）

### 查询 1 · 返回 0 行

```sql
SELECT payload FROM observations WHERE entity_id = ? AND metric_id = ? AND value_kind = ? AND period_kind = ? AND period_start IS NOT DISTINCT FROM ? AND period_end = ? AND source_snapshot_id IN (SELECT source_snapshot_id FROM sources WHERE available_at <= ? AND source_snapshot_id IN (?) AND company_id IN (?)) AND available_at <= ? AND status = 'candidate' ORDER BY record_id LIMIT 257
```

| 参数位置 | 绑定值 |
| --- | --- |
| 1 | google-cloud |
| 2 | revenue |
| 3 | actual |
| 4 | year |
| 5 | 2022-01-01 |
| 6 | 2022-12-31 |
| 7 | 2026-09-22 |
| 8 | alphabet-2025-10k-c2f63010 |
| 9 | alphabet |
| 10 | 2026-09-22 |

### 查询 2 · 返回 0 行

```sql
SELECT payload FROM observations WHERE entity_id = ? AND metric_id = ? AND value_kind = ? AND period_kind = ? AND period_start IS NOT DISTINCT FROM ? AND period_end = ? AND source_snapshot_id IN (SELECT source_snapshot_id FROM sources WHERE available_at <= ? AND source_snapshot_id IN (?) AND company_id IN (?)) AND available_at <= ? AND status = 'candidate' ORDER BY record_id LIMIT 257
```

| 参数位置 | 绑定值 |
| --- | --- |
| 1 | google-cloud |
| 2 | operating\_income |
| 3 | actual |
| 4 | year |
| 5 | 2022-01-01 |
| 6 | 2022-12-31 |
| 7 | 2026-09-22 |
| 8 | alphabet-2025-10k-c2f63010 |
| 9 | alphabet |
| 10 | 2026-09-22 |

### 查询 3 · 返回 0 行

```sql
SELECT payload FROM observations WHERE entity_id = ? AND metric_id = ? AND value_kind = ? AND period_kind = ? AND period_start IS NOT DISTINCT FROM ? AND period_end = ? AND source_snapshot_id IN (SELECT source_snapshot_id FROM sources WHERE available_at <= ? AND source_snapshot_id IN (?) AND company_id IN (?)) AND available_at <= ? AND status = 'candidate' ORDER BY record_id LIMIT 257
```

| 参数位置 | 绑定值 |
| --- | --- |
| 1 | google-cloud |
| 2 | revenue |
| 3 | actual |
| 4 | year |
| 5 | 2022-01-01 |
| 6 | 2022-12-31 |
| 7 | 2026-09-22 |
| 8 | alphabet-2025-10k-c2f63010 |
| 9 | alphabet |
| 10 | 2026-09-22 |

### 查询 4 · 返回 0 行

```sql
SELECT payload FROM observations WHERE entity_id = ? AND metric_id = ? AND value_kind = ? AND period_kind = ? AND period_start IS NOT DISTINCT FROM ? AND period_end = ? AND source_snapshot_id IN (SELECT source_snapshot_id FROM sources WHERE available_at <= ? AND source_snapshot_id IN (?) AND company_id IN (?)) AND available_at <= ? AND status = 'candidate' ORDER BY record_id LIMIT 257
```

| 参数位置 | 绑定值 |
| --- | --- |
| 1 | google-cloud |
| 2 | operating\_income |
| 3 | actual |
| 4 | year |
| 5 | 2022-01-01 |
| 6 | 2022-12-31 |
| 7 | 2026-09-22 |
| 8 | alphabet-2025-10k-c2f63010 |
| 9 | alphabet |
| 10 | 2026-09-22 |
