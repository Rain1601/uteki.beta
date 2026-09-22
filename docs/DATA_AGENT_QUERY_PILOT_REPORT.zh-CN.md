# Data Agent 第一轮查询闭环：执行报告

日期：2026-09-22。**已完成本地候选数据上的 schema 发现 → 参数化 SQL 取数 → Decimal 计算 → 文档补证据闭环。** 本轮执行已解析的结构化查询计划；自然语言 question 保留研究意图，尚未接入自主规划模型。没有新增模型调用、外部取数、部署或自动采纳。

后续进展：自然语言规划现已实现并完成两轮小范围真实验证，详见 [自然语言查询验收报告](DATA_AGENT_NL_CANARY_REPORT.zh-CN.md)。该验收发现并修复了期间猜测和文档节点问题，全面铺开门槛仍未通过；下文保留原类型化查询试点的历史范围与结果。

入口：[运行摘要](../experiments/data_agent_query/2026-09-22-pilot-04/summary.json)、[可查询 Schema](../experiments/data_agent_query/2026-09-22-pilot-04/step-01/schema.json)、[来源与覆盖目录](../experiments/data_agent_query/2026-09-22-pilot-04/step-01/coverage.json)。

当前查询契约为 `research-query-v0.3`。完整复查与修订见 [代码 Review 报告](DATA_AGENT_CODE_REVIEW.zh-CN.md)。文档公司、记录实体必填；可查实体来自数据集；缺数判断按公司、材料类型和期间隔离。构建入口必须显式传入 [来源与适配器配置](../experiments/data_agent_query/specs/alphabet-reviewed-v1.json)，其中固定来源和输入 hash。

当前入口已更新到 pilot-04。旧 pilot-01（v0.1）和 pilot-02（v0.2）原样保留；当前运行时拒绝旧版数据集，使用新版目录及其 snapshot_id。当前抽取适配器仍限定于其声明的 Alphabet 来源，双公司合成测试验证的是查询执行层，不代表多公司真实材料的抽取已完成。此前 `alphabet` 默认值已在 v0.2 修复，本轮检查并修复了其余同类边界问题。

## 1. 处理范围

数据版本为 `query-c9e2d02426106321794973a3`。载入 4 份既有冻结来源：Alphabet 2025 10-K、2026 Q1/Q2 10-Q、2025 Q4 电话会。

数据包括 24 条保持原值的确定性财务记录、12 条改写 prompt 第一次运行的电话会候选，以及从已有原文生成的 1 条独立 FY2026 投资构成定性展望。合计 **37 条候选记录、52 个证据对象**；包含同一指引的重复披露，不等于 37 个独立事实。

原始材料、索引、规范化记录、证据与 DuckDB 投影固定在新目录；校验源 hash、索引绑定、证据原文与产物 hash。原有源文件和实验结果未回写。此前 hash 不一致的 earnings release 继续排除。源已冻结不等于新记录已获采纳，默认查询仍要求显式允许 candidate。

2025 Q2 数值在本次数据集中来自 2026 Q2 报告比较列，可用日期按该来源记录，不冒充 2025 年当时已载入的原始披露。此为有限投影，不代表全公司、所有指标或整篇电话会已经结构化。

## 2. Step 1：统一可查询的语义

新契约见 [query_contract.py](../src/uteki/domain/research_data/query_contract.py)，并输出 [记录 Schema](../experiments/data_agent_query/2026-09-22-pilot-04/dataset/schemas/record.schema.json)、[请求 Schema](../experiments/data_agent_query/2026-09-22-pilot-04/dataset/schemas/query.schema.json)、[结果 Schema](../experiments/data_agent_query/2026-09-22-pilot-04/dataset/schemas/result.schema.json)。

| 之前的表达 | 本轮表达 | 边界 |
| --- | --- | --- |
| value=50，摘要才写 just over half | `value_relation=gt`、`denominator=total_ml_compute`、`modality=expected` | 50 是阈值；接近程度保留在原话，不变成精确比例 |
| 40 years，摘要中有 could / or longer | `gte` 与 `modality=could`；期间 not_applicable | 可能的建筑寿命，不是保证所有组件至少用 40 年 |
| FY2026 大体相似附着于 FY2025 记录 | 独立 `investment_mix_outlook`、FY2026、qualitative、无数值 | 只依据明确原话和年份，不复制 60/40 为精确预测 |
| Cloud 未来展望是 statement、period=null | management_guidance、period_resolution=unresolved | 不猜目标期间，返回 partial 与缺口 |
| 财务 XBRL 维度写法不同 | 同一 `reporting_segment=google-cloud` | 只映射已声明的 Cloud/OperatingSegmentsMember，原维度保留，未知维度拒绝 |
| USD_billions 与 value | USD 基础单位与 Decimal，原尺度保留在 origin | 单位规范化不属于预测，财务原值不变 |

逐条前后对照：[normalization-diff.json](../experiments/data_agent_query/2026-09-22-pilot-04/step-01/normalization-diff.json)。这些是新契约与显式规范化规则，不是一次新的 prompt 实验，也不能归为新的 Claude prompt 收益。

指标字典说明定义、单位、分母、别名及禁止隐式求和。覆盖目录区分当前可查候选、权限过滤、来源存在但本试点未结构化、来源缺失和截止日期不可用。未命中不会变成“公司未披露”。

## 3. Step 2：SQL 取数与确定性计算

DuckDB 1.5.5 的数值列使用 `DECIMAL(38,12)`；公式由 Python Decimal 执行，内部精度 50，输出 6 位小数、展示 2 位小数。超出支持范围或精度会拒绝，避免静默舍入。

每个快照一个独立数据库，Port 校验请求 snapshot_id 与数据库 manifest 一致。SQL 由预定义编译器产生并绑定参数，查询连接只读，关闭外部访问与扩展自动加载，限制线程、内存、执行时间和结果行数。不开放任意 SQL。

实际财务用例，金额单位为百万美元：

| 单季期间 | 收入 | 营业利润 | 营业利润率 |
| --- | ---: | ---: | ---: |
| 2025 Q2 | 13,624 | 2,826 | 20.74% |
| 2026 Q2 | 24,768 | 8,814 | 35.59% |

收入同比 **81.80%**，营业利润同比 **211.89%**，利润率提升 **14.84 个百分点**。2026 H1 收入 44,796 单独返回，未混入 Q2 计算。

首次检查发现收入与营业利润的原始 XBRL 分组轴不同，导致可比性检查拒绝计算。现只对已确认的同一报告分部建立语义映射；原始维度保留，未知维度继续拒绝。没有删除所有维度来强行计算。

每项计算记录公式版本、操作数 record IDs、单位、舍入与快照。同比基期/收入分母非正、期间不可比、冲突或缺数时返回缺口。相同数值的重复披露保留来源，不重复加入操作数。

可查看：[请求](../experiments/data_agent_query/2026-09-22-pilot-04/step-02/financial/request.json)、[结果与证据](../experiments/data_agent_query/2026-09-22-pilot-04/step-02/financial/result.json)、[SQL 参数与执行记录](../experiments/data_agent_query/2026-09-22-pilot-04/step-02/financial/trace.json)。

## 4. Step 3：同一请求内查数与读原文

混合用例返回 FY2026 CapEx 175–185 十亿美元的 CEO/CFO 两条披露、Cloud ML 算力的 gt 50% 记录，以及投资构成“大体相似”的独立定性记录。两位管理层的指引不相加。

检索 `timing of cash payments` 后读取附近同一说话人上下文，保留供给、组件价格、付款时间三项限定及原始指引；检索 `just over half` 后读取完整 QA-06，包括分析师问题和全部管理层回答。

可查看：[混合请求](../experiments/data_agent_query/2026-09-22-pilot-04/step-03/mixed/request.json)、[混合结果](../experiments/data_agent_query/2026-09-22-pilot-04/step-03/mixed/result.json)、[取数和阅读轨迹](../experiments/data_agent_query/2026-09-22-pilot-04/step-03/mixed/trace.json)。

这里的 complete 只表示类型化计划执行完整。关键词匹配不保证自然语言问题已获得完整语义回答；检索仍为字面匹配。达到搜索上限或上下文过长时明确返回 limited/定位信息，不静默截断后声称完成。

## 5. 实际状态与验证

| 用例 | 结果 |
| --- | --- |
| 财务取数与 5 项计算 | complete |
| CapEx + ML 算力 + Q&A 混合读取 | complete |
| 2026 Q2 电话会 | unanswerable / source_missing |
| 本试点未结构化的 Cloud 毛利润 | unanswerable / source_present_unprocessed；不宣称未披露 |
| 截至 2026-07-22 查本快照中的 2026 Q2 数值 | unanswerable / not_available_at_cutoff；不返回数值或证据 |
| 未显式允许候选 | unanswerable / quality_filtered |
| 目标期间未确定的 Cloud 展望 | partial / target_period_unresolved |

7 组请求和结果均已保存。共 36 项查询/范围测试覆盖上述行为、重复披露不放大操作数、冲突阻止计算、零分母、期间/精度约束、只读与外部访问限制、篡改检测、Python/CLI 一致性。连同已有财务、文档与交接检查均已验证；完整测试范围与结果见本轮 Review 报告。

来源和产物 hash 见 [run-manifest.json](../experiments/data_agent_query/2026-09-22-pilot-04/run-manifest.json)。用例由本任务构造并验证，不是独立盲评，也不是两个独立模型的端到端测试。

## 6. 其他 Agent 如何使用

Python 接口为 `QueryDataPort.discover_data / get_schema / query_data / get_evidence / read_context`，见 [query_service.py](../src/uteki/infrastructure/research_data/query_service.py)。JSON CLI 共用同一实现，原 ResearchDataPort/v0.1 发布包保留。

新环境安装锁定的 data extra：`uv sync --locked --extra analysis --extra data`。当前虚拟环境已安装新增依赖，可直接运行：

```bash
.venv/bin/python scripts/query_research_data.py schema \
  --dataset experiments/data_agent_query/2026-09-22-pilot-04/dataset \
  --metric revenue

.venv/bin/python scripts/query_research_data.py query \
  --dataset experiments/data_agent_query/2026-09-22-pilot-04/dataset \
  --request experiments/data_agent_query/2026-09-22-pilot-04/step-02/financial/request.json
```

Agent 先读 schema/覆盖，再选择实体、指标和期间，提交 records/documents/calculations 计划。请求固定快照、截止日期与候选策略。只有 question、没有计划时拒绝执行，不把未解析的问题默认为已回答。安装项目后也可用 `uteki-data` 入口。

复现整个试点，用新目录执行：

```bash
.venv/bin/python scripts/run_data_query_pilot.py --output /tmp/uteki-query-new-run
```

已存在目录会拒绝覆盖。新 clone 仍需恢复原始材料和上次实验输入；本轮没有发布本机数据。

## 7. 剩余工作

自主自然语言规划、OCR、Web/供应商获取、自动补数、MCP/HTTP 接入及跨公司/独立 Agent 评测仍待实施。下一步应让 Analysis Agent 根据工具 schema 自主生成和修正计划，并在未参与规范化的样本上评估。

本轮交付了可复用的本地查询执行底座，没有宣称完整 Text2SQL 或多来源 Data Agent 已完成。旧抽取实验 Step 5 的连接/未知费用状态保持原样，本轮未重启收费运行。
