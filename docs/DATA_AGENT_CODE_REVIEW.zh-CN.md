# Data Agent 代码 Review 与修订报告

日期：2026-09-22。审查对象是本轮 Data Agent 的完整数据处理与查询调用链，并延伸到它依赖的旧读取/发布接口、DeepSeek 接入和实验入口。**发现了多处将 Alphabet 试点范围隐式用于通用逻辑的问题，现已修复；查询执行层已用独立双公司数据验证。真实材料的抽取仍需要显式、经过验证的适配器。**

## 1. 审查范围

- 契约与执行：`query_contract.py`、`query_service.py`、`query_dataset.py`、`query_cli.py`、旧 `models.py` / `local.py`。
- 数据上游：财务 XBRL 解析、电话会抽取、抽取 prompt / 校验器、规范化、DocumentReader 与来源/证据绑定。
- 旧试点：`artifacts.py`、`cloud_spike.py`、`cloud_llm.py`、`cloud_recovery.py`；保持既有快照与采纳状态。
- 调用与运行：查询/抽取/consumer 实验脚本，DeepSeek adapter、凭证加载、费用记录相关改动，测试及文档示例。

这是本轮数据链路的代码审查；项目完整离线测试也已执行。没有逐文件重审整个前端，没有联网核验供应商当前价格，也没有重新调用模型。离线模型测试使用模拟 HTTP。

## 2. 发现与处理

| 优先级 | 原问题与影响 | 修订及验证 |
| --- | --- | --- |
| P1 | `get_schema` 和 `_lookup` 固定只认 Alphabet / Google Cloud；换数据集仍展示旧实体，拒绝有效新公司 | 实体与公司归属从当前来源表和 observations 生成；跨公司重名实体拒绝并要求限定 ID。独立合成 Acme / Other 数据集验证 schema、查询、计算和来源归属 |
| P1 | 缺数诊断仅按期间寻找来源，会把别家公司的来源算作请求公司的覆盖 | 按实体所属公司、截止日期、材料类型过滤；实际财务指标只考虑财报，比较列按同实体及完整期间匹配。验证另一公司和电话会均不会造成虚假的财务覆盖 |
| P1 | 构建器固定实验目录、给所有来源写入 Alphabet、取第一份电话会，再套用所有 prompt 产物 | 新增必填 [构建配置](../experiments/data_agent_query/specs/alphabet-reviewed-v1.json) 和 `DatasetBuildSpec`；每个输入显式绑定 source ID、company/entity、adapter、SHA256；核对来源身份、期间、可用日期、记录归属与证据。没有默认配置，也没有第一份材料 fallback |
| P1 | prompt 指定 Alphabet 实体，电话会 Guidance 写死公司，财务 parser 写死 CIK / Cloud 映射 | prompt 从 `packet.entity_catalog` 选择实体并校验越界归属；电话会调用必须传公司与支持的 fiscal calendar；财务调用必须传 `FinancialMapping`，XBRL context 校验其 issuer。Alphabet 映射独立放入命名适配器 |
| P1 | 财务查询校验日期后仍按原始字符串比较；`20260204` 可错误通过 `2026-02-05` 的 cutoff | 将日期解析为 date 后比较；加入紧凑 ISO 格式回归，验证提前一天仍不返回数据 |
| P1 | 旧缺数接口把任意 request_id 拼到文件路径，存在目录穿越与检查后覆盖窗口 | 限制为安全 ID，使用独占创建，保留相同内容幂等行为，拒绝不同内容和符号链接；验证路径输入被拒绝 |
| P2 | 特定电话会的年份/措辞修正看似通用；60%/40% 比例即使与 value 不符也可能被标为 approx | 迁入 `adapters/alphabet_query.py`，校验固定已审阅来源 hash、公司和实体；输入文件 hash 由显式构建配置固定；比例值必须与已审阅原句一致。验证其他来源、其他公司及错误比例都被拒绝 |
| P2 | 旧发布器仍会对任意输入套用 Alphabet FY2025 的政策/期间，并覆盖已有目录 | 必须显式选择旧适配器，验证其冻结来源与公司；CLI 必填输入及目标目录，拒绝覆盖。Cloud 旧试点也增加固定来源检查；原历史样本的发布字节一致性测试通过 |
| P2 | 合法查询累计超过 256 个证据 ID 会被单次工具上限拒绝；非法 Decimal 文本抛底层异常 | 内部按最多 256 个 ID 分批读取，保持逐次 cutoff/候选校验；非法数值转为契约验证错误。验证 300 个证据完整返回 |

前一轮已经修复的 `DocumentRequest.company_id="alphabet"` 默认值继续保持移除；本轮也补齐了记录实体与计算实体的非空约束。

## 3. 允许的常量与禁止的隐式范围

[AGENTS.md](../AGENTS.md) 已加入仓库约束，核心是：

1. 通用契约、查询、parser、prompt、生产入口不得把公司、期间、来源、实验目录或预期答案设为隐式默认值；移到常量或配置后继续默认使用也不合规。
2. 范围必须来自已验证请求、来源元数据或明确选择的版本化适配器；缺失/冲突返回错误或缺口。
3. 取数、覆盖、计算、证据及缺数诊断保持一致的公司、期间、政策和 cutoff 范围。
4. 公司/XBRL 映射和样例语义修正放在命名适配器，并校验来源；实验具体值只能用于明确标注的实验范围。评测答案不得进入抽取逻辑。
5. 修改范围契约时同步检查调用方、Schema、历史兼容性，并用原样本之外的公司/期间验证行为。

公式 ID、协议枚举、单位、已注明的 provider endpoint、资源上限可以是常量。当前支持的 calendar fiscal periods、USD 财务抽取等限制仍明确存在；没有将不支持的财年或币种静默解释成支持的类型。

旧 Cloud spike 与 FY2025 发布器仍含具体公司/年份，它们是有来源校验的历史专用适配器，不能视为新通用入口。下一家公司的接入需要新映射及真实来源测试。

## 4. 验证与前后对照

执行完整离线回归：

```bash
.venv/bin/python scripts/run_offline_checks.py --integration
```

最终结果：**470 项 Python 测试、7 项 JavaScript 测试通过**。其中查询与范围测试 36 项，覆盖原真实冻结数据和独立双公司合成数据；其余包含财务解析、文档读取、prompt、旧发布/恢复、模拟 DeepSeek 请求、费用及项目现有回归。

最新快照为 `query-c9e2d02426106321794973a3`，契约 `research-query-v0.3`：

- [可查询 Schema](../experiments/data_agent_query/2026-09-22-pilot-04/step-01/schema.json)
- [来源与覆盖](../experiments/data_agent_query/2026-09-22-pilot-04/step-01/coverage.json)
- [7 组查询结果摘要](../experiments/data_agent_query/2026-09-22-pilot-04/summary.json)
- [完整性与前后对照校验](../experiments/data_agent_query/2026-09-22-pilot-04-verification.json)

重建保留 4 份来源、37 条候选记录、52 个证据对象。与修订前 pilot-02 相比，来源、证据、数值、计算操作数和计算规则不变；7 组查询状态一致。记录契约版本、快照 ID 和绑定快照的计算 ID 随版本变更。原始文件和 pilot-01/02/03 保留，未自动采纳。

这证明范围修订没有改变既有样例的财务结果，并不证明模型抽取质量有提升。本轮没有新的模型费用，也没有将旧 prompt 实验重新执行。

## 5. 调用迁移

查询使用最新数据目录，先 discover/schema 再提交明确实体和期间的计划：

```bash
.venv/bin/python scripts/query_research_data.py schema \
  --dataset experiments/data_agent_query/2026-09-22-pilot-04/dataset

.venv/bin/python scripts/query_research_data.py build \
  --repo . \
  --spec experiments/data_agent_query/specs/alphabet-reviewed-v1.json \
  --destination /tmp/uteki-query-reviewed-new
```

目标目录必须不存在。API `build_dataset` 同样要求 `spec=`。旧 v0.1/v0.2 快照不由当前运行时静默升级；历史文件仍可对照查看。

财务抽取 API 要求 `mapping=`；电话会抽取要求 `company_id=` 和 `fiscal_calendar=`。新 prompt 准备协议为 v0.2，必须含实体目录；旧 prepared 包若需要执行，应在新目录准备，旧包会在模型调用前被拒绝。

## 6. 仍未完成的能力

自然语言自主规划、OCR/Web 获取、多币种/非日历财年及多公司真实材料抽取仍未实现。当前指标字典和两个查询规范化适配器保持明确范围；不存在通过改公司参数即可自动理解任意公司的承诺。

部分定性电话会规则是对冻结原文的人工审阅式规范化，仍需独立样本评估。候选记录、证据支持度和最终采纳也继续分开处理。本次修订解决的是范围正确性、可复用接口和明确失败行为。
