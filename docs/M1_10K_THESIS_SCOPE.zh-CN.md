# M1 范围——Alphabet 10-K 有界经营 Thesis

## 状态

已于 2026-09-13 通过用户审核，并于同日根据 Data Agent / Analysis Agent 职责澄清完成修订。中文文件为规范性文件；英文配套文件必须保持语义一致。M1 尚未成为当前实施里程碑，也不得打断 M0 的 Business Map Benchmark、Baseline、评分和 Experiment 001。

## 评测问题

> 给定 Data Agent 从 Alphabet FY2025 10-K 生成的版本化 EvidenceBundle，以及经过人工审核的 Business Map，Analysis Agent 能否通过受控的 ResearchDataPort 查询，形成一份有证据、有因果关系、可证伪且可持续验证的 10-K 有界经营 Thesis Candidate？

固定研究问题为：

> 仅根据 Alphabet FY2025 10-K，哪一个经营论点最能解释 Alphabet 当前如何创造价值，以及未来三年最可能决定该经营轨迹增强或削弱的三个关键驱动是什么？

## 产物定义

M1 的产物称为 `10-K Bounded Operating Thesis Candidate`，不是最终 Investment Thesis。

它可以表达：

- 基于 10-K 的 Primary Bet；
- 最多三个关键经营 Driver；
- 最多两个会破坏 Primary Bet 的关键 Risk；
- 每个 Driver 和 Risk 对应的可执行 To Watch；
- 支持证据、反对证据、推断、假设和未知问题；
- 明确的三年研究期限和版本时间点。

它不得表达：

- 当前市场预期或 Variant Perception；
- 当前估值、目标价或预期收益率；
- 买入、卖出、仓位或交易建议；
- 10-K 提交日之后的经营变化；
- 没有来源支持的“最新情况”；
- 仅凭模型置信度升级为事实的判断。

没有市场预期和价格的结论只能称为经营 Thesis，不能称为完整投资 Thesis。

## 固定输入

- 公司：Alphabet Inc.；
- 文件：截至 2025 年 12 月 31 日财年的 Form 10-K；
- 提交日期：2026 年 2 月 5 日；
- SEC Accession：`0001652044-26-000018`；
- 数据来源边界：冻结的 Alphabet FY2025 10-K Source Snapshot；
- Data Agent 输入索引：`alphabet_2025_10k/indexes/v0.1`；
- Analysis Agent 直接输入：Data Agent 发布的不可变 `data_snapshot_id` 和 `evidence_bundle_ids[]`；
- 事实底座：M0 发布并经过人工审核的 Business Map 版本，由 ResearchDataPort 提供；
- 外部材料：禁止；
- 互联网检索：禁止；
- 模型先验知识：不能作为事实证据。

每次运行必须记录具体的 `data_snapshot_id`、`evidence_bundle_ids[]`、`business_map_version` 和研究问题版本。底层 `source_snapshot_id` 与 `document_index_id` 通过 EvidenceBundle 保留完整溯源，但不是 Analysis Agent 绕过 Data Agent 的直接输入。M0 的 Business Map 未冻结前，不得生成正式 M1 Baseline。

Data Agent 与 Analysis Agent 的具体交接规则以
[`DATA_ANALYSIS_AGENT_CONTRACT.zh-CN.md`](DATA_ANALYSIS_AGENT_CONTRACT.zh-CN.md)
为准。

## 最小研究流程

```text
Frozen 10-K
→ Data Agent Processing
→ Versioned Research Data / EvidenceBundle
→ Research Question
→ Research Data Query Plan
→ Active ResearchDataPort Queries
→ Primary Bet and Driver Candidates
→ Risk and Counter-Evidence Challenge
→ To-Watch Candidates
→ Thesis Synthesis
→ Human Review
→ Versioned Candidate
```

这些步骤必须形成独立运行记录。第一版不得用一个 Prompt 同时读取整份 10-K 并直接输出最终 Thesis。

## LLM 调用边界

### R0——检索计划

输入：

- 固定 Research Question；
- 任务契约和来源边界；
- ResearchDataPort 发布的数据目录、可查询数据类型与来源范围；
- 已审核 Business Map 的摘要、对象标识与版本；
- 当前可用 EvidenceBundle 的标识和覆盖范围。

输出：

- 建议执行的 ResearchDataQuery；
- 需要读取的 Business Map、Claim、Metric、Evidence 或 Document Context；
- 需要寻找的事实类型；
- 暂时无法回答的问题。

R0 不得输出最终 Thesis。

### R1——主动研究数据查询

Analysis Agent 使用只读 ResearchDataPort 查询 Data Agent 已发布的研究数据。Data Agent 可以在内部使用 Document Navigator 解析节点、Block 和表格；Analysis Agent 不得直接解析 SEC HTML，也不得绕过 ResearchDataPort 读取底层文件。

输出：

- ResearchDataQuery 标识和返回的 EvidenceBundle 标识；
- 被读取的 Business Map、Claim、Metric、Evidence 和 Document Context 标识；
- 证据候选及其可回溯的 Source Locator；
- 检索失败和未找到结果；
- 完整工具调用 Trace。

R1 是可重复进入的查询循环，而不是只执行一次的预处理。R2–R4 如果发现证据缺口，只能创建 `ResearchDataRequest`。Data Agent 完成请求并发布新的 EvidenceBundle 后，流程重新进入 R1；Analysis Agent 不能自行解析来源或补全事实。

### R2——Primary Bet 与 Driver Candidate

输入：

- Research Question；
- 已审核 Business Map；
- R1 取得的证据；
- Driver 输出 Schema。

输出一条 Primary Bet 草案和最多三个互不重复的 Driver。Primary Bet 必须直接回答 Research Question；每个 Driver 必须说明经营机制、可能的财务影响、时间范围、支持证据、反对证据和未知问题。

三个是输出槽位上限，不是强迫填满的数量。证据不足时必须保留空缺或 Unknown，不得用低质量内容补足。

### R3——Risk 与反方挑战

输入：

- Research Question；
- Primary Bet 草案；
- Driver Candidates；
- 与风险、竞争、资本配置和不确定性有关的证据。

输出最多两个关键 Risk。每个 Risk 必须包含失败机制、受影响 Driver、支持证据、反对证据和候选 Kill Criteria。不得把 Item 1A 的标题或宽泛风险直接当作 Thesis Risk。

### R4——To Watch

输入：

- Driver Candidates；
- Risk Candidates；
- 固定来源中可识别的指标、披露和未来验证路径。

每个 Driver 和 Risk 至少对应一个 WatchItem；若无法根据当前材料定义可执行的观察方法，必须明确标记 `not_observable_from_current_scope`。

### R5——Thesis Synthesis

输入只包括：

- Research Question；
- 已审核 Business Map；
- R2–R4 的结构化 Candidate；
- 支持和反对 Evidence；
- Material Unknowns。

输出一份结构化 Thesis Candidate。R5 不得重新引入未经前序步骤记录的新事实。

## ResearchDataPort 查询契约

M1 向 Analysis Agent 最多提供以下只读能力：

```text
get_business_map(company_id, version)
search_research_data(company_id, query, source_policy_id)
get_claim_evidence(claim_id)
get_metric_series(metric_id, periods)
get_document_context(evidence_ids)
compare_periods(company_id, periods, data_types)
request_missing_data(research_data_request)
```

规则：

1. ResearchDataPort 只能返回符合指定 `source_policy_id` 的已发布数据；
2. 每个事实必须携带稳定的 Data Object 标识、版本及 Source Locator；
3. 搜索结果不能自动成为 Evidence，Analysis Agent 必须引用 EvidenceBundle 中的具体 Evidence；
4. 每次调用记录参数、返回标识、顺序、耗时和失败；
5. 证据不足时，Analysis Agent 创建 `ResearchDataRequest` 或输出 Unknown；
6. Analysis Agent 不得通过模型记忆补齐来源缺口，也不得直接解析原始 SEC 文件；
7. Data Agent 新增或修正数据时发布新的不可变 EvidenceBundle，不修改既有 Bundle；
8. 相同数据快照、查询、工具版本和配置必须得到可复现的查询结果；
9. 第一版由本地文件实现 ResearchDataPort，不引入独立服务、PageIndex、向量数据库或开放网络搜索。

## 最小数据契约

### ResearchQuestion

- `question_id`；
- `question`；
- `company_id`；
- `horizon`；
- `decision_scope`：固定为 `operating_research`；
- `source_policy_id`；
- `version`。

### ThesisCandidate

- `thesis_id`；
- `version`；
- `source_as_of`：固定为 10-K 提交日；
- `created_at`；
- `question_id`；
- `primary_bet`；
- `conclusion`；
- `horizon`；
- `driver_ids[]`；
- `risk_ids[]`；
- `watch_item_ids[]`；
- `supporting_evidence_ids[]`；
- `contradicting_evidence_ids[]`；
- `unknown_ids[]`；
- `confidence`；
- `review_status`。

### DriverCandidate

- `driver_id`；
- `statement`；
- `mechanism`；
- `affected_business_ids[]`；
- `financial_impact`；
- `expected_direction`；
- `time_horizon`；
- `supporting_evidence_ids[]`；
- `contradicting_evidence_ids[]`；
- `unknown_ids[]`；
- `assertion_type`；
- `review_status`。

### RiskCandidate

- `risk_id`；
- `statement`；
- `failure_mechanism`；
- `affected_driver_ids[]`；
- `impact`；
- `candidate_kill_criteria[]`；
- `supporting_evidence_ids[]`；
- `contradicting_evidence_ids[]`；
- `assertion_type`；
- `review_status`。

### WatchItemCandidate

- `watch_item_id`；
- `linked_type`：`thesis | driver | risk`；
- `linked_id`；
- `question`；
- `observable`；
- `metric_or_signal`；
- `expected_direction`；
- `support_condition`；
- `warning_condition`；
- `falsification_condition`；
- `future_source_types[]`；
- `cadence`；
- `rationale_evidence_ids[]`；
- `review_status`。

### EvidenceLink

- `evidence_id`；
- `document_id`；
- `node_id`；
- `block_id`；
- `text_hash`；
- `quote`；
- `stance`：`supports | contradicts | context`；
- `supports_field`；
- `source_url`。

### Unknown

- `unknown_id`；
- `question`；
- `materiality`；
- `related_ids[]`；
- `reason_unanswered`；
- `next_source_type`。

### AgentRunRecord

- `run_id`；
- `task_type`；
- `question_id`；
- `data_snapshot_id`；
- `evidence_bundle_ids[]`；
- `research_data_query_ids[]`；
- `source_snapshot_ids[]`：由 EvidenceBundle 继承的溯源信息；
- `document_index_ids[]`：由 EvidenceBundle 继承的溯源信息；
- `business_map_version`；
- `model_provider`；
- `model_id`；
- `prompt_version`；
- `schema_version`；
- `configuration`；
- `tool_trace[]`；
- `raw_output_ref`；
- `structured_output_ref`；
- `code_revision`；
- `started_at`；
- `finished_at`；
- `cost`；
- `latency`；
- `warnings[]`；
- `failure`。

## 判断类型

所有实质性陈述必须标记为：

- `explicit_fact`：10-K 直接陈述；
- `derived_interpretation`：由明确证据和可说明的推理得出；
- `research_hypothesis`：需要未来材料验证的判断；
- `unknown`：当前固定来源不足以支持。

Thesis 和 Driver 通常属于 Interpretation 或 Hypothesis。引用多个事实不能自动把它们变成事实。

## 人工参考答案与 Benchmark

M1 不假设 Thesis 存在唯一正确措辞，也不使用字符串完全匹配建立 Gold Answer。

参考集流程：

1. 高能力 Agent 可以在 Baseline 之外提出 Reference 草案，但人工必须根据固定来源独立核验并最终裁决；
2. 对每个 Driver、Risk、WatchItem 和 EvidenceLink 逐项审核；
3. 保留被排除的候选及排除原因；
4. 明确记录允许的替代表述和歧义；
5. 冻结 Reference、Annotation Policy 和 Review Decisions；
6. 在 Reference 冻结前不得针对完整答案调整 Baseline Prompt。

## 评测维度

### 确定性指标

- Schema 合法率；
- Evidence Locator 解析率；
- 引用文本与来源一致率；
- 无证据事实率；
- 来源越界率；
- 工具 Trace 完整率；
- 输出数量约束和引用完整性；
- 重复 Driver/Risk 比例。

### 人工 Rubric

- Primary Bet 是否回答研究问题；
- Driver 是否重要、互不重复并具有清晰因果机制；
- Risk 是否会实质性破坏 Thesis，而非宽泛风险摘录；
- 是否同时寻找支持和反对证据；
- WatchItem 是否明确、可执行、可证伪；
- Unknown 是否诚实表达材料边界；
- 最终结论是否与前序结构一致；
- 作为后续研究起点是否有用。

客观指标与人工 Rubric 必须分开报告，不压缩成单一总分。M1 不评测未来回报、选股正确率或事后经营结果。

### 分层归因

评测必须保留两条独立链路：

1. Data Agent：从固定 10-K 到 EvidenceBundle，评测事实准确性、覆盖、结构、数值和 Evidence 定位；
2. Analysis Agent：从冻结且审核通过的 EvidenceBundle 到 Thesis Candidate，评测问题回答、Driver 选择、因果关系、反证、Risk 和 To Watch；
3. 端到端结果可以另行报告，但不得用一个总分掩盖两层错误，也不得把 Data Agent 的缺失计为 Analysis Agent 的推理错误。

## 版本与存储

第一版继续使用不可变 JSON 产物，不引入数据库：

```text
data/agent_runs/alphabet_2025_10k_thesis/<run_id>/
├── request.json
├── research_data_query_plan.json
├── research_data_trace.jsonl
├── evidence_bundles.json
├── evidence.json
├── drivers.json
├── risks.json
├── watch_items.json
├── thesis_candidate.json
├── raw_outputs/
└── manifest.json
```

经过审核的参考版本进入：

```text
benchmarks/alphabet_2025_10k_thesis/v0.1/
```

修正任何已审核内容必须创建新版本。动态 Observation、持续监控和 SQLite 状态存储属于后续 In-the-Flow 里程碑。

## 五道 Gate

### T0——Scope 与契约

审核研究问题、来源边界、Data/Analysis Agent 交接契约、ResearchDataPort、调用分段、评测 Rubric 和停止条件。

### T1——人工 Reference

在 Baseline 管线之外基于相同 10-K 建立一份 Reference Candidate。高能力 Agent 可以协助提出候选，但每项内容必须由人工独立核验和裁决；同时验证三 Driver、两 Risk 和 To Watch 的结构是否真正有用。

### T2——未经调优的主动检索 Baseline

冻结模型、Prompt、ResearchDataPort 版本、EvidenceBundle、配置和完整 Trace，运行一次最简单 Baseline。

### T3——评测与错误分析

比较 Baseline 与 Reference，先区分 Data Agent、交接契约、Analysis Agent 和 Benchmark 错误，再细分查询、证据、因果关系、Driver 选择、Risk、Watch、综合和 Schema 错误。

### T4——Experiment 001

只选择一个高影响错误类型，预先写出假设，只改变一个因素，并记录质量、成本和延迟变化。

## 验收标准

- 所有事实性前提均来自 EvidenceBundle，并可继续定位到固定 10-K Block；
- 所有 ResearchDataPort 调用均可重放并审计；
- Analysis Agent 不直接读取或解析 SEC HTML；
- 数据提取错误与分析推理错误可以独立归因；
- 最多三个 Driver、两个 Risk，且不为填满数量制造内容；
- 每个 Driver 和 Risk 都有支持证据、反方检查及 WatchItem，或明确说明不可观察；
- Thesis 没有引入前序步骤未记录的新事实；
- 外部知识、当前市场数据和投资建议为零；
- 人工审核者能够解释每项内容为什么被保留、修改或拒绝；
- 同一输入与配置可产生可比较的运行快照。

## 停止条件

出现以下任一情况时返回 T0：

- 需要外部材料才能回答固定研究问题；
- Driver 和产品、趋势标签或财务指标无法一致区分；
- Risk 退化为 Item 1A 摘要；
- WatchItem 没有实际可观察对象；
- Analysis Agent 依赖模型记忆而不是 EvidenceBundle 中的证据；
- Analysis Agent 绕过 ResearchDataPort 直接读取或解析原始 SEC 文件；
- 数据错误和分析错误无法根据版本与 Trace 分开归因；
- 一个超级 Prompt 取代了可诊断的分步运行；
- Thesis 被误称为当前投资建议；
- M1 实施妨碍 M0 完成。

## 明确延后

- 10-Q、电话会、新闻、投资者材料和竞争对手文件；
- 市场一致预期、Variant Perception 和估值；
- Bull/Base/Bear 目标价及概率加权收益；
- 催化剂日历和实时提醒；
- Observation、Thesis Update 和持续版本迁移；
- Portfolio Factor、仓位和交易计划；
- 多公司扩展；
- 多 Agent Team；
- PageIndex、向量数据库和开放网络搜索。
