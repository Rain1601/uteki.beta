# Data Agent：来源范围与文本读取完成报告

日期：2026-09-23

后续进展：第 2 项也已完成，见[统一证据包报告](DATA_AGENT_EVIDENCE_PACKAGE_REPORT.zh-CN.md)。以下保留第 1 项完成时的验证范围。

本轮完成的是 **TODO 1：明确来源范围，并把目录、章节读取和文本搜索接入 Data Agent**。现在可以指定一份或多份冻结材料，让 Agent 从目录开始取得原文；数值查询、计算和证据读取使用同一来源范围。TODO 2 的统一证据包、TODO 3 的任务覆盖检查尚未完成。

验证结果：**549 项 Python + 7 项 JavaScript 全部通过**，命令为 `.venv/bin/python scripts/run_offline_checks.py --integration`。本轮增加 45 项 Python 用例：18 项 scoped service、14 项 scoped Agent/SDK、10 项 CLI/运行器、3 项阅读分组。模型响应测试使用 HTTP mock；真实付费调用为 0。

## 前后变化

| 场景 | 原有行为 | 本轮行为 |
| --- | --- | --- |
| “依据这份 10-K 找业务和风险材料” | 新 Agent 主要通过指标查询、关键词查询和已知块读取取得材料；底层目录能力没有直接接入规划动作 | 可以先 `outline_source`，再选择章节 `read_source`，按游标继续；不必先制造一个数值查询 |
| 限定具体材料版本 | Agent 请求指定公司、数据集、截止日；没有统一的来源版本白名单 | `ExecutionScope` 必须显式给出公司与 `source_snapshot_ids`，适用于所有 scoped 工具 |
| 同公司多份披露 | 公司相同不能表达“仅依据指定年报”，可能包含另一份被数据集收录的材料 | SQL、计算依赖、证据、文档查找及缺数诊断均只使用选定来源 |
| 搜索与正文 | 搜索用来定位，然后取得上下文 | 新搜索接口只返回带定位信息的预览；目录和预览不进入可引用的正文 context 集合 |
| 连续阅读 | 底层已有块和 reading group 扩展 | 新接口提供绑定来源、章节、索引和执行范围的分页游标；明确返回正文、缺口或读取限制 |

这些变化没有把年报重新抽取成完整数据库，也没有改变候选数据的审批状态。

## 协议与入口

| 层次 | 版本 / 入口 | 职责 |
| --- | --- | --- |
| 冻结数据与旧查询契约 | `research-query-v0.3` | 保留原记录、查询和结果 Schema；本轮不重写历史快照 |
| 新执行范围 | `research-execution-v1` / `ExecutionScope` | 固定数据集、公司、来源版本、来源策略、截止日期和 candidate 访问权限 |
| 文档游标 | `document-cursor-v1` | 校验 scope、snapshot、source、index、node；搜索游标另外绑定 phrase 和 offset |
| 新 Agent 请求 | `data-agent-query-v0.3` / `ScopedAgentQuery`、`DataQueryAgent.run_scoped()` | 使用 `ScopedPlannerDecision` 调度来源受限的工具 |
| 兼容入口 | `data-agent-query-v0.2` / `DataQueryAgent.run()` | 保留旧调用与历史 canary 请求格式；不自动补选来源 |

Python 入口是 `QueryDataPort(dataset).scoped(scope)`。返回的接口包括 `get_schema`、`discover_data`、`query_data`、`get_evidence`、`read_context`、`outline_source`、`read_source` 和 `search_source`。

CLI 入口仍为 `scripts/query_research_data.py`，新增 `scoped-schema`、`scoped-discover`、`scoped-query`、`scoped-evidence`、`scoped-context`、`scoped-outline`、`scoped-read`、`scoped-search`；每个命令都必须传入 `--dataset` 与 `--scope`。涉及读取或搜索的请求继续用 `--request` 文件显式指定来源与章节；旧命令保持独立。

模型运行器 `scripts/run_data_agent_query.py` 按配置中的 `agent_schema_version` 选择新旧请求类型。新执行使用 `SdkQueryPlanner(scoped=True)` 对应的 Prompt 和输出 Schema；来源校验先于模型调用。本轮没有执行真实模型请求。

## 文本究竟如何返回

`outline_source` 返回源索引的章节结构，不表示正文已经读过。`search_source` 在选定节点内执行忽略大小写的字面匹配，按原文顺序分页返回定位预览；零匹配不能推断公司没有披露。

`read_source` 返回解析后保存的**完整原文块**及其原有元数据，不按字符截断一个段落或表格。reading group 会补齐同组列表、邻近表格说明和电话会 Q&A。块内已有的表格结构、说话人和页码等信息随块保留；这不等于新增 OCR、重新识别原图或保证原始版式完全还原。

调用者必须选择来源与节点。未指定起始块表示从**该节点**开始；指定中间块也可以读取。`next_cursor` 用于继续，`node_complete=true` 仅表示这次读取到达节点末尾，**不能证明节点此前所有块都已阅读，也不能证明研究问题已经完整覆盖**。

范围错误、来源晚于截止日、未开放 candidate、缺失节点、超大原子上下文都会返回错误或明确 gap。完整组跨越所选节点时，接口返回 `context_crosses_node`，空正文且不推进；调用者需要显式选择包含该上下文的节点。当前单次正文结果上限为 80,000 字节，超限返回 `context_too_large`，不截断原文来伪装读取成功。

读取显式选定材料不再要求问题额外声明一个数值期间。指标查询仍须使用问题中明确的观测期间；年报所属期间不能自动充当其中每条历史指标的期间。当前数值期间支持仍限于已声明的自然年/季度能力。

## Review 中修复的问题

1. **重叠组遗漏。** 原 `DocumentReader.read()` 单遍遍历可能先跳过列表组，再因表格说明扩展进入该列表，漏掉后续条目。改为重叠范围固定点扩展，保留原组顺序和节点边界；用真实组生成逻辑及不同组排列测试传递与嵌套情况。
2. **跨节点组被部分返回。** scoped 章节读取额外检查跨节点的完整组，返回明确 gap，不把局部片段当作完整上下文。
3. **空 context 被引用。** scoped 的旧式文档查询路径曾把 `context_too_large` 且 `blocks=[]` 的结果注册成 context。现在只注册 `status=read` 且正文非空的结果；错误仍保留在 gaps。兼容入口的既有行为未借此重写。
4. **再次设定 scope 扩权。** scoped port 的派生范围只允许相同或收窄：来源/公司只能取子集，截止日期不能增加，candidate 权限不能从 false 升为 true；构造派生 scoped facade 同样受检查。原始根 port 仍可按调用者明确输入创建新的执行范围。

## 验证证据与适用边界

测试覆盖独立的合成公司、同公司多份来源与修订版本、跨公司隔离、未来来源、候选权限、计算与证据一致性、目录/搜索/正文区分、游标错配、完整组及超限行为，并运行旧查询和 Agent 回归。合成数据的预期答案不进入生产抽取或归一化逻辑。

已生成并核验 [7 步离线示例](../experiments/data_agent_query/source-scope-v1/offline-01/README.md)：目录返回 28 个节点；业务正文读取 4 个块并续读 4 个块；风险搜索返回 2 个字面命中，随后读取 2 个完整块；SQL 返回 2 条候选记录，计算 Google Cloud 2025 年营业利润率为 23.69%；最后按真实工具 ID 汇总引用。所有数据来自显式选定的 `alphabet-2025-10k-c2f63010`。脚本化 planner 只验证执行编排和产物可追溯性，不能证明真实模型能自主选对章节或完整理解材料。

复现命令（输出目录必须未创建，且不得位于不可变 dataset 内）：

```bash
.venv/bin/python scripts/verify_scoped_retrieval.py \
  --spec experiments/data_agent_query/source-scope-v1/replay-spec.json \
  --output /tmp/uteki-scoped-replay
```

示例保存了逐步输入、决策、原文、SQL、计算、游标和引用；已检查产物哈希与完整源快照文件哈希，并在临时目录重跑获得一致结果。预设步骤只属于这个显式离线样例，不传给真实模型。

本轮没有进行真实模型验收，没有完成“依据 FY2025 Google 10-K 分析重点业务和关键风险”的完整研究问题验收，没有证明多公司端到端抽取泛化。现有 Alphabet 专用归一化适配器、指定源哈希修复、USD 与自然年等限制仍在；来源范围与读取执行的通用性，不能替代抽取质量评测。此前保存的 gap 仍保守保留，不自动因后续搜索或读取而判定已经解决。

既有自然语言期间解析仍采用有限语法，例如英文句末 `FY2031.` 暂不能识别为年度，会要求澄清；本轮没有扩展该语法。显式章节读取不依赖此数值期间识别。完整年报的多轮阅读还受 12 步和上下文大小上限约束，后续覆盖台账必须保留未读范围，而不能把到达上限当成完成。

## 后续顺序

**TODO 2：统一证据包。** 用新版本契约区分原始文本、表格/标量、模型提取或摘要、图片引用，统一来源版本、页码/块/区域、派生关系、候选状态和缺口。摘要关联原文，图片引用明确是否经过 OCR/视觉理解；保留历史快照可读。

**TODO 3：任务覆盖。** 把研究问题拆为待回答事项与所需材料，记录章节哪些块已读、哪些未读、数值依赖是否满足、条件和反例是否遗漏；区分到达章节末尾、完成阅读与完成问题。完成统一证据包后再建立该层验收，并在明确预算内安排真实模型与完整问题验证。
