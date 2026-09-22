# Data Agent 自然语言查询：首轮真实验收报告

日期：2026-09-22。**已实现并完成小范围真实验收；查询闭环跑通，全面铺开的验收门槛尚未通过。** 两轮各运行同样的 3 个问题，发现并修复了期间猜测和文档节点假设问题；电话会查询的相关性、缺口归属仍需修正。

两轮合计 **12 次 DeepSeek 请求，公开单价估算 USD 0.0536937，新增未知费用 0 次**。达到授权请求数上限后停止。旧实验那笔未知费用仍为 unknown，没有算作零、结清或移入新预算。

入口：[逐题机器核验与轨迹](../experiments/data_agent_query/canary-v1/review.json)、[第一轮](../experiments/data_agent_query/canary-v1/live-01/result.json)、[修复后复验](../experiments/data_agent_query/canary-v1/live-02/result.json)。

## 1. 这次实际完成了什么

之前执行的是人工给出的 records/documents/calculations 查询计划。这次入口接收自然语言问题和调用方明确授权的公司、快照、截止日期、候选数据权限，由模型读取 schema、指标字典、实体与来源覆盖后自行提交计划。应用执行本地工具，再把结果或错误交回模型；模型可以继续查数、读原文、澄清或提交结果引用。

流程为：**自然语言 → 类型化计划 → 参数化 SQL / 文档检索 → 确定性计算与证据 → 模型选择结果引用**。财务值直接返回数据库记录或 Decimal 计算结果，不由模型重新抄写或心算。没有开放任意 SQL。

新代码：

- [agent_query.py](../src/uteki/domain/research_data/agent_query.py)：自然语言请求、计划、动作与结果引用契约；当前 `data-agent-query-v0.2`。
- [data_query_agent.py](../src/uteki/agents/data_query_agent.py)：有步数、上下文和时间上限的循环；应用固定业务范围，校验引用，保存每一步。
- [data_query_model.py](../src/uteki/agents/data_query_model.py)：接入现有 Agents SDK、DeepSeek JSON 模式、调用计量及历史费用检查。
- [period_scope.py](../src/uteki/domain/research_data/period_scope.py)：从问题文字识别明确年份/季度，并在执行前核对计划期间。
- [run_data_agent_query.py](../scripts/run_data_agent_query.py)：冻结配置、预检、执行与共享预算账本；多次运行累计请求数受限。

这次验证使用之前的 **4 份冻结 Alphabet 来源、37 条候选记录、52 个证据对象**。数据快照仍为 `query-c9e2d02426106321794973a3`，数据契约仍为 `research-query-v0.3`。没有重跑抽取或采纳候选记录。原 pilot 的 **59 个已登记产物 hash 全部保持一致**。

此前改写 Claude 风格抽取 prompt 的产物作为现有电话会候选数据被消费；本次是查询规划与执行验证，**不能把本次结果归为新的 Claude 抽取收益**。

## 2. Step 1：第一轮真实运行，先暴露问题

每题最多 4 步，合计用了 7 次请求。模型输入没有预写计划或验收答案；[验收参考](../experiments/data_agent_query/canary-v1/review-reference.json)单独留在评估目录。

| 问题 | 实际结果 | 判断 |
| --- | --- | --- |
| Google Cloud 2026 Q1 收入、营业利润、利润率，附来源 | 最终 `answered`；首步原文检索发生 `KeyError`，第二步去掉文档搜索后查数成功，第三步提交引用 | 数值正确，但绕过失败搜索不等于检索工具正常 |
| 2025 Q4 电话会给出的 FY2026 CapEx 范围及影响因素 | `partial`；取到范围和全部三项限定，同时多查了无关指标及宽泛关键词 | 内容已在证据中，查询相关性和完成状态不合格 |
| 未给期间的 Google Cloud 营业利润率 | `answered`；模型自行选了 2023/2024/2025 全年并计算 | **失败：不允许从覆盖目录补用户没有指定的期间** |

第一轮没有把“程序有返回值”算作通过。第三题还证明：prompt 已写明不猜期间、脚本化模型测试也能通过，仍不足以保证真实模型遵守。

## 3. Step 2：根据失败原因修复

**文档节点修复。** 原查询服务把文档根节点 ID 固定写为 `document`。电话会索引恰好使用这个 ID，10-K/10-Q 则使用各自索引中的完整 ID，导致真实财报检索失败。现在按索引元数据寻找唯一 `kind=document` 节点；没有或多个根节点都拒绝执行，不回退到猜测名称。搜索和回读统一使用此规则。

除真实 10-K/10-Q 检索测试外，还验证了独立节点名、缺失节点和重复根节点。并将第一轮失败的原始计划原样作[离线回放](../experiments/data_agent_query/canary-v1/offline-original-plan-replay.json)：现在能返回文档上下文及相同财务计算。宽泛搜索仍可能产生检索上限提示，这是查询范围问题。

**期间执行约束。** 原来只有模型行为约定；现在应用从问题本身生成允许的期间集合，模型选择的记录、计算期间以及文档报告期必须在该范围内。缺少可识别期间时要求澄清，错误季度不能进入 SQL。规则不读取样本覆盖，不包含公司、财年或目标数值默认值。

这是刻意收窄的首版能力：支持明确的日历年和季度，例如 `FY2031`、`2031 年`、`2031 Q2`、`Q2 2031`、`2031 年第二季度`。相对期间、YTD、日期区间、非日历财年，以及隐含同比基期尚不在此自然语言解析范围；需澄清。底层类型化查询支持的期间比这个入口更多。它还不是完整的时间语义解析器。

**查询 prompt 修订。** 先查题目需要的指标，再阅读记录自带的 evidence / qualifier evidence；有未满足的问题才补充原文检索，避免无关指标引入缺口。未加入本题答案、关键词或特定公司补丁。后续真实复验表明，这项 prompt 修订还没有充分解决过度查询。

## 4. Step 3：相同问题复验

保留第一轮产物，冻结[新的配置和代码 hash](../experiments/data_agent_query/canary-v1/prepared-refinement/manifest.json)，在同一预算账本内最多再执行 5 次请求。每题最多 2 步，最后一题剩 1 步；两轮步数限制不同，因此只能作行为对照，不能视为严格的 prompt A/B 实验。

| 问题 | 修复后实际结果 | 当前验收 |
| --- | --- | --- |
| Q1 财务题 | 2 次请求：查数/计算 → 提交引用；无执行错误、无缺口 | **通过该用例** |
| 电话会 CapEx 题 | 2 次请求；范围及三项限定仍正确，但仍多查指标和无匹配关键词，保留 2 个缺口，结果 `partial` | **尚未通过完整性与相关性要求** |
| 缺少期间 | 1 次请求，主动 `needs_clarification`，无取数、无计算 | **澄清动作通过；解释文字仍需约束** |

财务结果为收入 **USD 20,028,000,000**、营业利润 **USD 6,598,000,000**，确定性计算利润率 **32.94%**。期间是 2026-01-01 至 2026-03-31，证据来自冻结 10-Q 的原文表格与 XBRL 上下文；计算产物包含公式版本、操作数 ID 和舍入规则。

电话会结果为 FY2026 管理层 CapEx 指引 **USD 175–185 billion**，不是实际支出。CEO/CFO 两条重复披露保留各自证据，不相加。CFO 限定原文完整存在于被引用记录的 qualifier evidence：

> Keep in mind that the availability of supply, pricing of components, and timing of cash payments can cause some variability in the reported CapEx number.

即供给可获得性、组件价格和现金付款时间。该证据定位为电话会 PDF 第 13 页、`block-000153-938fcda2`。

第三题的澄清文字另有问题：模型说覆盖“2025Q1–2026Q2 各季度/YTD”，但目录没有 2025 Q3/Q4；当前 NL 入口也不支持 YTD。没有因此返回错误数值，不过这说明**自由文本中的覆盖声明仍可能失真**。本轮未将这个问题掩盖为完全通过。

每步文件可直接对照：

| 用例 | 首轮目录 | 复验目录 |
| --- | --- | --- |
| Q1 财务 | [result](../experiments/data_agent_query/canary-v1/live-01/q1-margin/session/result.json) | [result](../experiments/data_agent_query/canary-v1/live-02/q1-margin/session/result.json) |
| CapEx | [result](../experiments/data_agent_query/canary-v1/live-01/capex-conditions/session/result.json) | [result](../experiments/data_agent_query/canary-v1/live-02/capex-conditions/session/result.json) |
| 缺少期间 | [result](../experiments/data_agent_query/canary-v1/live-01/clarify-period/session/result.json) | [result](../experiments/data_agent_query/canary-v1/live-02/clarify-period/session/result.json) |

各 session 内含 `catalog.json`、`turn-NN/input.json`、`decision.json`、工具结果或错误反馈、最终引用及 hash 清单；相邻 `costs.json` 保存逐次调用的用量和估算。

## 5. 费用、测试与证据核验

| 运行 | 财务题 | 电话会题 | 澄清题 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 首轮请求数 | 3 | 2 | 2 | 7 |
| 首轮估算 USD | 0.0107193 | 0.0122601 | 0.0107331 | 0.0337125 |
| 复验请求数 | 2 | 2 | 1 | 5 |
| 复验估算 USD | 0.0075957 | 0.0094332 | 0.0029523 | 0.0199812 |

累计估算 **USD 0.0536937 / 授权 USD 0.20**；累计请求 **12 / 12**。无在途请求、新未知费用或失败模型请求。金额依据 usage 和已记录的 DeepSeek 公开单价，未应用缓存折扣，**不是供应商账单**。新账本为 `experiments/data_agent_query/canary-v1/approved-budget.sqlite`，不能通过更换输出目录重置这笔额度。

旧 `consumer-deepseek-02` 的未知请求继续保留，其原预留估算为 USD 0.0166125，实际费用未知。预检只对用户明确允许保留的那一笔旧记录放行；新未知记录仍会阻止继续。

验证结果：

- **492 项 Python 测试、7 项 JavaScript 测试通过**；`git diff --check` 通过。
- 新增/本轮查询 Agent 相关 **22 项测试**：包含独立 Acme/Other 合成数据、公司/截止日期/候选权限隔离、错误计划纠正、伪造引用、步数/上下文上限、期间猜测阻断、索引节点差异与真实原文回读。
- SDK 的 HTTP mock 测试只验证协议与计量；真实能力结论来自上述 12 次请求，二者不混算。
- [离线评估脚本](../experiments/data_agent_query/canary-v1/review.py)核对所有返回 evidence 的 quote 与冻结原文块、上下文块与索引、来源 hash、财务值、公式与操作数，并验证历史产物未变化。参考答案没有进入规划输入。

本轮问题由本任务选定、来源与数据集已知，不是独立盲评。单公司、少量问题通过不代表多公司、多语言、自由问题或长期运行可靠；没有新增外部源、OCR、Web 检索、自动补数、MCP/HTTP 服务或独立 Analysis Agent 端到端验收。

## 6. 技术方案需要调整的地方

下一步应先修 **“子问题—证据—未完成项”契约**，再扩大数据量或问题数。CapEx 案例已经显示数据里有答案，问题在于模型多查了什么、把什么认作未完成。

1. **问题拆解要可追踪。** 为每个用户子问题建立 requirement ID，工具请求声明服务于哪个 requirement；结果引用逐项对应，避免返回一包数据就称已回答。语义关联仍需评估，ID 本身不是完整性证明。
2. **区分检索诊断与答案缺口。** `no_literal_match` 是一次搜索的诊断；无关指标的 `target_period_unresolved` 不能自动变成用户问题缺数。保留所有检索轨迹，但最终未完成项需要关联具体 requirement。不能仅凭模型一句“已解决”删除真实缺口，也不能简单把 `partial` 改成 `answered`。
3. **引用粒度支持限定证据。** 目前 answer part 引用整条 record，原始 qualifier 已返回，但下游还要自行定位。增加直接引用 evidence ID 及其角色，明确区分金额、条件、分析师问题与管理层回答；不丢失原文。
4. **澄清与覆盖展示由结构化目录约束。** 模型只声明缺少哪个字段；可选期间和能力列表从实际目录与入口能力生成，避免虚构连续覆盖或推荐尚不支持的查询格式。

这些是下一阶段的具体修改项，本轮没有宣称已经实现。先用当前电话会问题、空检索但其他证据足够、真实缺证据、限定遗漏，以及另一公司的合成场景验证；通过后再做独立真实材料和另一 Agent 消费测试。

**阶段状态：自然语言查询的首轮验证已完成，发现了真实问题并做了定向修复；全面铺开门槛未通过，当前应继续收敛查询与证据交付契约。**
