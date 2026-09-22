# Data Agent / Analysis Agent 交接契约 v0.1

## 状态

已于 2026-09-13 根据用户确认的职责边界形成。中文文件为规范性文件，英文配套文件必须保持语义一致。该契约先约束设计，不要求立即拆分仓库、进程或服务。

## 核心边界

```text
原始研究材料
    ↓
Data Agent
    ↓
版本化 Research Data
    ↓ ResearchDataPort
Analysis Agent
    ↓
Thesis / Drivers / Risks / To Watch
```

Data Agent 负责“材料说了什么”。Analysis Agent 负责“这些事实对研究问题意味着什么”。两者不能在同一输出中混写。

## Data Agent 所有权

Data Agent 负责：

- 原始材料获取、Hash、来源和时间；
- 10-K、10-Q 等文档的结构化与索引；
- Block、Table、Asset 和原文定位；
- Business Map、事实 Claim、财务指标和跨期变化；
- Evidence Link、解析诊断、缺失和数据质量；
- 每次数据处理的模型、Prompt、工具、配置和 Trace。

Data Agent 不负责 Thesis、Driver 优先级、Risk 判断、估值或买卖建议。

## Analysis Agent 所有权

Analysis Agent 负责：

- Research Question；
- Primary Bet；
- Key Drivers 和因果机制；
- Thesis Risks、反方论证和 Kill Criteria；
- To-Watch 验证协议；
- Operating Thesis Candidate 及其版本；
- 新 EvidenceBundle 对既有判断的影响。

Analysis Agent 不得直接解析原始 SEC HTML、重写 Data Agent 事实、隐藏来源缺口或把模型先验当作 Evidence。

## ResearchDataQuery

Analysis Agent 的每次查询包含：

- `query_id`；
- `company_id`；
- `question`；
- `requested_data_types[]`；
- `periods[]`；
- `source_policy_id`；
- `related_research_ids[]`；
- `minimum_evidence_level`；
- `created_at`。

查询表达研究需要，不指定 Data Agent 的内部 Pipeline、Prompt 或模型。

## EvidenceBundle

Data Agent 返回一个不可变 Bundle：

- `bundle_id`；
- `query_id`；
- `source_policy_id`；
- `data_snapshot_id`；
- `source_snapshot_ids[]`；
- `document_index_ids[]`；
- `business_map_version`；
- `claims[]`；
- `metrics[]`；
- `changes[]`；
- `evidence_links[]`；
- `document_context[]`；
- `unknowns[]`；
- `quality_diagnostics[]`；
- `generated_at`。

每个 Claim、Metric 和 Change 必须通过 Evidence Link 回到 Source Snapshot。Bundle 可以包含原文摘录供分析和人工审核，但原始文档结构仍由 Data Agent 管理。

## 缺失数据请求

如果 EvidenceBundle 不足以支持判断，Analysis Agent 返回 `ResearchDataRequest`：

- `request_id`；
- `research_question`；
- `missing_information`；
- `why_material`；
- `suggested_source_types[]`；
- `company_id`；
- `periods[]`；
- `related_driver_or_risk_ids[]`；
- `priority`；
- `status`。

Data Agent 可以完成、部分完成、拒绝或标记当前来源不可回答。它必须生成新的 Bundle 或明确的 Unknown，不能静默覆盖旧 Bundle。

## Analysis Agent 可用接口

第一版只提供：

```text
get_business_map(company_id, version)
search_research_data(company_id, query, source_policy_id)
get_claim_evidence(claim_id)
get_metric_series(metric_id, periods)
get_document_context(evidence_ids)
compare_periods(company_id, periods, data_types)
request_missing_data(research_data_request)
```

这些接口由 `ResearchDataPort` 定义，可以由本地文件、SQLite 或未来服务实现。Analysis Agent 不依赖具体存储。

## 版本规则

1. Analysis Run 固定引用一个或多个 `bundle_id`；
2. EvidenceBundle 创建后不可修改；
3. Data Agent 修正事实时创建新的 `data_snapshot_id` 和 Bundle；
4. Analysis Agent 不会因底层数据更新而自动改变已发布 Thesis；
5. 新数据只能产生 Analysis Update Candidate，人工审核后形成新 Thesis Snapshot；
6. 所有结果同时保存 `source_as_of` 和实际 `created_at`。

## 错误归属

- 原文下载、解析、表格、数值、实体、时间对齐或 Evidence 定位错误：Data Agent；
- 查询表达不清或请求了不存在的数据：交接契约；
- 在正确数据上选择了错误 Driver、因果推理错误、忽视反证或错误综合：Analysis Agent；
- 人工 Reference 或评分规则不一致：Evaluation；
- 无法由允许来源回答：Unknown，不记为任一 Agent 的事实错误。

## 硬性规则

- Data Agent 与 Analysis Agent 分别保存运行记录并分别评测；
- Analysis Agent 引用的事实必须来自 EvidenceBundle；
- Analysis Agent 可以主动查询 Research Data，但不能绕过 Port 访问原始材料；
- Data Agent 可以使用 LLM 处理材料，但其推断必须标记并接受数据评测；
- Gold Answer、Review Decision 和评测分数不得进入任何被测 Agent 的输入；
- 第一版保持模块化单体，不因逻辑分层提前拆服务。

## 产品界面归属

`/result` 是 Data Agent 已发布 `EvidenceBundle` 的只读可视化检查器。Business
Map 只是该结构化数据的一种视图；页面不代表 Gold Benchmark，也不展示
Analysis Agent 的 Thesis、Factors、Risks 或 To Watch。
