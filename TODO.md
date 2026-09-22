# 开发待办与交接

更新：2026-09-22。代码基线：`f8af66b`。以下为待开发/待验收项，不表示已经实现，不改变现有 M0 研究验收状态。

## 接下来先完成什么

先跑通一个包含文档阅读与取数的大问题，再验证跨公司迁移：

> 根据 Alphabet FY2025 10-K，分析重点业务和关键风险，并提供可核查依据。

这是显式登记的验收样例，不得成为通用接口的默认公司或期间。只使用选定年报及其版本；不能混入后续季度、电话会或网络材料。

| 顺序 | 待办 | 产物与验收标准 |
| --- | --- | --- |
| 1 | [ ] 接通章节阅读与统一来源范围 | 将已有 `DocumentReader.outline/read/search` 接入新 Data Agent。支持按章节续读、返回下一批位置、保留完整列表/表格/限定条件；来源版本约束同时作用于原文读取、SQL 和计算依赖。跨公司、跨来源、越界读取被拒绝，缺失章节明确返回缺口。 |
| 2 | [ ] 定义统一证据包 | 区分原始文本、表格/标量、模型提取/摘要和图片引用；统一来源版本、页码/块/区域、派生关系、覆盖状态和缺口。原话不被摘要替代；图片引用不等于已具备 OCR/视觉理解。使用新版本契约，保持历史快照可读。 |
| 3 | [ ] 补齐任务拆解与 ReAct 完成条件 | 显式记录子任务、证据需求、依赖、状态及完成条件；执行工具后按结果补查/纠错。保存已读/未读范围、冲突和未满足要求。区分任务完成、部分完成和达到上限；不能仅凭模型 `finish` 就声称全文覆盖。先验证顺序执行，无需为每个子任务创建独立 Agent。 |
| 4 | [ ] 验收上述完整问题 | 冻结来源、验收问题和检查表，先离线验证工具，再开展另行明确预算的真实模型验收。检查 Business、Risk Factors、MD&A 和相关附注的阅读范围，核对业务/风险分析证据、数值口径、遗漏和重复。保存逐步过程、证据包、分析结果与未完成项，报告模型声明与实际覆盖的差异。 |
| 5 | [ ] 验证跨公司泛化 | 建立显式适配器注册和能力声明，逐步解除构建器对 Alphabet 适配器/指标目录的直接依赖。事先登记至少一家不同财年公司和一家不同业务结构公司，从原文完整跑到入库与查询。检查币种/尺度、财年、分部维度、指标定义、证据和遗漏；未知映射保持 unresolved。查询层的合成数据测试不能代替端到端验收。 |

Analysis Agent 负责研究维度、业务重要性与风险影响判断；Data Agent 负责拆分证据需求、读取/取数/处理及覆盖说明。Text2SQL 是其中一项能力，任务可同时消费文本、表格和图片引用。

## 后续排队

- [ ] 新数据更新批次：来源版本登记 → 新增/修订/重复/冲突差异 → 校验 → 显式发布候选快照。保留历史输入，新快照不自动替换旧分析。
- [ ] 在更新批次验收后增加来源发现、增量获取与调度；当前没有自动增量同步。
- [ ] 按真实问题接入图片读取、OCR/视觉理解及高质量外部来源；保留原图与派生产物的对应关系。
- [ ] 分别评估解析遗漏、提取语义保真和来源可追溯性。引用匹配通过、块数或数据库行数均不能代替全文召回率。

## 当前已完成的基线

- [x] 参考 Claude Financial Services 改写抽取 prompt，接入 DeepSeek；保留原话、期间、尺度、条件和 Q&A 归属。
- [x] 建立 DuckDB/Schema、受约束查询计划及多轮工具反馈；当前仍有财年、币种和适配器范围限制。
- [x] 保存 4 份来源、37 条候选记录、52 个证据对象及两轮自然语言查询样例；不是全文结构化或所有用例均通过。
- [x] 展示问题、SQL 和实际结果；提供数据库表格、Schema、逐行溯源、信息损耗与更新机制说明。
- [x] 禁止共享接口中的隐式业务默认值；增加来源/公司隔离、精度、证据和快照校验。
- [x] 504 项 Python、7 项 JavaScript 检查通过，已提交个人 GitHub。工程检查通过不代表研究采纳或泛化验收。

## 换机器后从这里开始

在个人仓库检出目录中执行；有本地未提交改动时先核对，避免覆盖：

```bash
git pull --ff-only
uv sync --locked --extra analysis --extra data
.venv/bin/python scripts/check_workspace.py
.venv/bin/python scripts/run_offline_checks.py --integration
```

默认 `run_offline_checks.py` 只跑既有 portable core，未包含全部新增 Data Agent 用例；上面的 `--integration` 包含完整 Python 回归和 JavaScript 检查。离线检查、查看历史数据与 UI 不需要 API Key。

工作区检查通过后启动：

```bash
PYTHONPATH=src:. .venv/bin/python -m apps.review_workbench.app --host 127.0.0.1 --port 8765
```

- 数据库与溯源：`/companies/alphabet/data/dataset?collection=nl-canary-v1`
- 查询样例：`/companies/alphabet/data/queries?collection=nl-canary-v1&run=live-02&case=q1-margin`
- 当前查询快照：`query-c9e2d02426106321794973a3`，目录为 `experiments/data_agent_query/2026-09-22-pilot-04/dataset`。
- 仓库已包含部分公开来源、索引、查询快照和历史运行；其它未提交资料以检查结果为准，不假设全量历史工作区已恢复。旧 `review_excerpt.json` 第 90 段仍有已知指纹问题，不修改原件或重写 hash 来消除告警。
- `.env`、费用账本和含本机路径的运行元数据留在本地，不随 Git 同步。后续真实调用须在新机器单独配置个人密钥，并核对/恢复相关费用状态。
- 上轮自然语言验收额度已用满 **12/12 次请求**。继续开发不等于批准新的付费请求；真实模型验收前另行明确问题范围、预算和调用上限。不得复制旧授权、新建空账本或更换输出目录来重置额度。
- 继续使用个人 GitHub 身份与个人 noreply 提交邮箱，凭据、内部信息和本机身份路径不入库。界面按正常桌面视口验收，不主动切换手机/H5 视口。

## 代码与记录入口

- [数据溯源、更新及多模态设计说明](docs/DATA_AGENT_DATA_LINEAGE_AND_UPDATES.zh-CN.md)
- [自然语言查询验收报告](docs/DATA_AGENT_NL_CANARY_REPORT.zh-CN.md)
- [文档阅读器](src/uteki/agents/document_reader.py)、[阅读上下文分组](src/uteki/agents/reading_groups.py)
- [Data Agent 执行循环](src/uteki/agents/data_query_agent.py)、[规划契约](src/uteki/domain/research_data/agent_query.py)
- [查询与计算执行](src/uteki/infrastructure/research_data/query_service.py)、[数据契约](src/uteki/domain/research_data/query_contract.py)
- [快照构建](src/uteki/infrastructure/research_data/query_dataset.py)、[显式输入配置](src/uteki/infrastructure/research_data/query_inputs.py)
- [已登记展示数据](data/query_views/nl-canary-v1.json)

继续开发时从第 1 项开始；每完成一项，更新勾选状态、验证产物和未解决边界。
