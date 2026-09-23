# Data Agent 统一证据包完成报告

日期：2026-09-23。

本轮完成 TODO 第 2 项：把 Data Agent 已经取得的数据组织为独立版本的证据包。后续 Agent 可以判断每个产物是什么、从哪里来、经过什么处理，以及哪些内容仍未处理。没有执行新的模型请求，也没有完成整份年报的研究分析。

验证结果：**592 项 Python、7 项 JavaScript 全部通过**。本轮新增 43 项 Python 用例，覆盖契约、组装、处理来源、报告及篡改/路径越界回归。执行命令：`.venv/bin/python scripts/run_offline_checks.py --integration`。另已核验旧阶段产物、冻结来源和新运行 manifest 的哈希，并在临时目录重跑得到完全相同的证据包。新增真实模型请求为 0。

## 现在会交付什么

`DataQueryAgent.run_scoped()` 的每次新运行自动保存：

- `evidence-package.json`：`retrieval-evidence-v1` 证据包。
- `evidence-package.schema.json`：可直接读取的 JSON Schema。
- 原有 `result.json`：继续保存工具结果和引用，新增证据包版本、ID 与相对路径。
- 原有 `manifest.json`：包含新产物的文件哈希。

包内统一保存来源范围、公司与来源版本对应表、产物、派生引用、旧执行 ID 对应关系、返回范围和缺口。`context:`、`evidence:`、`record:`、`computed:` 使用各自命名空间，避免不同类型的旧 ID 恰好相同而串联。

| 类型 | 含义 | 后续 Agent 应如何使用 |
| --- | --- | --- |
| `source_text` | 原封保留的解析文本块，含页码、说话人等已有字段 | 可以引用；属于解析后文本，不等于原 HTML/PDF 的全部版式 |
| `source_table` | 完整表格块和已有行列、合并单元格、表头等结构 | 保留单位、表头和证据单元格；不是模型重建的表 |
| `source_quote` | 数据库内的引文及字符、单元格等定位 | 连接原文/原表格；无法定位时明确降为仅快照验证 |
| `image_reference` | 图片定位、替代文字、资产元数据和字节取得状态 | 替代文字不是 OCR；即使字节核验通过，也不代表已理解图片 |
| `normalized_record` | 原有期间、数值关系、单位、分母、条件、归一化摘要与原始记录 | 按 `origin_kind` 区分确定性处理、模型辅助和未知来源；摘要不是原话 |
| `computed_scalar` | 注册公式计算结果、精度和全部操作数 | 沿父记录追溯，不能为计算值伪造一段原文引语 |
| `model_extract` | 历史产物中保留的原始模型提取输出 | 与后续归一化分开，保留原单位、原摘要和引用 |
| `model_summary` | 单独定义的模型摘要类型 | 必须引用父产物，不能冒充原文；本轮未新增摘要生成器或实际摘要输出 |

已有旧 `EvidenceBundle`、`research-query-v0.3` 和历史运行文件保持原协议。新证据包是独立输出，没有修改 DuckDB 表结构或重新发布候选快照。

## 真实性如何保证

Schema 校验结构与包内关系：类型和 payload 一致，引用闭合且无环，来源不能越过 scope，候选权限与 cutoff 一致，计算操作数必须对应归一化父记录。图片 OCR/视觉状态目前只允许 `not_run`；缺失定位、来源或处理信息必须显式表达。

打包器再核对冻结数据，而不是仅信任传入 JSON 或 Schema：

1. 重新校验并加载 `sources.json`、源索引、块文件及其 manifest；整块比较文字、表格和说话人等字段，防止工具返回对象的修改污染缓存后冒充原件。
2. 数据库引文和记录必须与所选快照一致；能定位的引文核对连续原话、字符范围和表格单元格。原数值关系、区间及条件不会被改写为点估计。
3. 计算结果重新通过同一个来源范围内的注册公式核验，连接全部操作数。
4. 图片只允许读取冻结数据集 manifest 已记录的文件；不会顺着旧相对路径去其它目录借图，也不会请求远端链接。
5. 历史处理方法只按原构建配置中的完整 artifact/source/hash 绑定和已登记 adapter 分类；未知方法保持未知，不按文件名、摘要、公司或记录 ID 猜测。

这些检查证明产物与选定快照的关系，不证明模型提取语义完整、财务口径一定正确或原文解析没有遗漏。独立收到一个包时仍应核验其发布 manifest 和来源；Schema 本身不能证明实际阅读历史或外部文件真实性。

## 阅读范围不再混为一谈

| 状态 | 实际含义 |
| --- | --- |
| `body_returned` | 工具明确返回的文本/表格块 |
| `provenance_only` | 为核验引文而补充进包的来源块，未因此自动算作规划 Agent 已阅读全文 |
| `navigation_only` | 目录或搜索定位，未返回完整正文 |
| `image_reference_only` | 图片引用，不能计为 OCR 或视觉阅读 |

同一块可能先被工具返回，又成为其它证据的出处；消费者应按来源和块 ID 去重。包始终标记 `semantic_completeness=not_evaluated`，尚未建立第 3 项的任务完成条件、未读范围台账和缺口消解逻辑。

## 真实离线样例

样例显式选定 FY2025 10-K 和 2025 Q4 电话会两份冻结来源，以六个预设步骤读取、取数和汇总。步骤不传给真实模型，也不构成自主分析能力验收。

产物包括 9 个文本块、3 个原表格、7 条引文、1 个图片引用、4 条归一化记录、1 个计算和 2 份历史模型原始提取输出。两次管理层 CapEx 指引披露均保留，没有把两次披露累计相加：

- Google Cloud 2025 年营收 `58,705,000,000 USD`，营业利润 `13,910,000,000 USD`；注册公式输出营业利润率 `23.69%`。
- 2026 年 CapEx 指引原模型单位为 `USD_billions`，值为 `175–185`；归一化记录为 `175,000,000,000–185,000,000,000 USD`，同时保留条件原话。
- 年报图片保留原刊第 26 页定位和资产元数据，字节状态为 `metadata_only`，OCR/视觉理解均未执行。

真实缺口也一起交付：图片字节不在冻结数据集中；历史模型 provider/model/prompt 哈希缺失；PDF 块 bbox 的单位未在当前协议中独立确认，因此保留坐标并明确未验证单位，不把整块 bbox 说成引文精确框。

可直接查看[人可读产物报告](../experiments/data_agent_query/evidence-package-v1/offline-01/evidence-report-v2.md)，以及 [样例运行步骤](../experiments/data_agent_query/evidence-package-v1/offline-01/README.md)、[证据包](../experiments/data_agent_query/evidence-package-v1/offline-01/session/evidence-package.json) 和 [Schema](../experiments/data_agent_query/evidence-package-v1/offline-01/session/evidence-package.schema.json)。

## 接口与复现

Python 使用 `build_evidence_package(scoped_port, result)`，可将历史 `run_scoped()` 结果生成新包；不原地修改旧结果。`scoped-schema` 的 `output_contracts.evidence_package` 暴露新 Schema。CLI 的 `scoped-package` 要求明确 `--dataset`、`--scope` 和 `--request`（历史 scoped result 文件）。

重新执行离线样例与生成可读报告，输出路径必须不存在：

```bash
.venv/bin/python scripts/verify_scoped_retrieval.py \
  --spec experiments/data_agent_query/evidence-package-v1/replay-spec.json \
  --output /tmp/uteki-evidence-package-replay

.venv/bin/python scripts/inspect_evidence_package.py \
  --package /tmp/uteki-evidence-package-replay/session/evidence-package.json \
  --output /tmp/uteki-evidence-package-report.md
```

下一步是 TODO 第 3 项：为一个研究问题定义子任务、证据需求和完成条件，记录已读/未读范围、未满足要求和冲突，区分任务完成、部分完成与到达上限。当前包提供这层工作的输入，不将模型 `finish` 当成研究问题已经完成。
