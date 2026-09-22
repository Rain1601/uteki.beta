# Claude 抽取指令改写：真实对照结果

日期：2026-09-22。**抽取层 12 次真实 DeepSeek 调用已完成；有局部改善，尚不支持整体替换 Uteki 解析器。下游 Step 5 首轮有一次截断，完整重跑又遇到连接错误，未完成验证。所有结果均为实验候选。**

已配套提供提取产物交互展示：财务指标、管理层指引、电话会 Q&A，支持两组 prompt / 两次重复切换、逐条原文与限定查看，以及前后变化对照。默认改写组第一次为 20 条记录，含同一指引的重复披露；展示范围为本次 3 个固定片段，并非全篇或所有公司。由 [生成脚本](../scripts/build_extraction_visualization.py) 直接读取冻结 JSON，无新增模型调用。展示释义与原始 JSON 分开，未将有歧义的 `value=50` 画成精确预测。验证记录见 [可视化复核](../experiments/research_data_quality/2026-09-22-visualization-review.json)。

## 1. 结论与当前建议

Claude Financial Services 的抽取要求值得部分采用：它们让模型更稳定地将单位依据、供给限制与原始记录关联，也减少了把“明年大体相似”直接展开成两个精确百分比预测的倾向。但财务数值在两组中本来就正确，不能宣称数值准确率因此提升；“略高于一半”等表达仍暴露了共同数据契约的缺口。

建议继续使用现有表格/XBRL 路径处理可确定的财务值，将经过改写的 prompt 用作电话会语义抽取的候选方案。正式接入前优先补齐比较符、近似程度、实际/预测身份与期间表达，再用新的材料验证。不能只依靠加长 prompt 来确保数值可被 Agent 安全消费。

## 2. 这次实际复用了什么

固定参考版本为 Anthropic 官方 `financial-services` 仓库提交 `574ed3624aebd0418c7e96cd101262f30210ab26`。原文件、来源链接、hash 与 Apache-2.0 许可已随实验保存，见 [upstream.json](../experiments/research_data_quality/2026-09-22-prompt-protocol/upstream.json)。此次运行使用 DeepSeek，没有调用 Claude 模型或供应商 API。

| 官方指令来源 | 原要求 | 本次改写 |
| --- | --- | --- |
| [Earnings Preview Phase 2](../experiments/research_data_quality/2026-09-22-prompt-protocol/upstream/earnings-preview.md) | 逐字原话、speaker、context；guidance、drivers、headwinds、Q&A themes | 对给定范围抽取相关记录，保留原话和说话人，并关联条件；不限定为四条报告用引语 |
| [Transcript Reader](../experiments/research_data_quality/2026-09-22-prompt-protocol/upstream/transcript-reader.yaml) | 材料不可信指令边界；reported figures、guidance、Q&A；schema JSON | 共用 Uteki 实验 schema，由宿主保存并校验证据；不采用其过于粗粒度的 actuals 字典作为最终契约 |
| [Tear Sheet Data Integrity](../experiments/research_data_quality/2026-09-22-prompt-protocol/upstream/tear-sheet.md) | 不混期间、缺失不猜、财务输入与计算分开、保存中间数据 | 对原始表格保持主体/期间/单位，禁止抽取阶段添加增长率或利润率；落盘由宿主对两组统一执行 |

**Uteki 自己补充的部分**：同说话人语境与主题边界、非量化指引、限定条件到记录的关系、比例分母、原文 block ID 校验。结果是“Claude 公开要求 + Uteki 改写”的整体效果，不能把增益全部归因于某一条官方 prompt。

直接查看两份完整提示词：

- [基础抽取 prompt](../experiments/research_data_quality/2026-09-22-prompt-protocol/prompts/control.txt)
- [Claude 要求改写版 prompt](../experiments/research_data_quality/2026-09-22-prompt-protocol/prompts/claude_adapted.txt)
- [共同 JSON schema](../experiments/research_data_quality/2026-09-22-prompt-protocol/schema.json)

基础组是为相同任务和 schema 编写的对照，**不是历史 Uteki prompt 的原样重放**。现有确定性规则另作能力参照。

## 3. 分步执行与输入修正

| 阶段 | 完成事项 | 产物 |
| --- | --- | --- |
| 输入审计 | 原 A1 包只有表格，漏了前一句 `(in millions)`；将同一段原文补入前后双方，数据记录数值未变 | [candidate-05](../experiments/research_data_quality/2026-09-22-candidate-05/manifest.json) |
| 冻结方案 | 固定来源、两个 prompt、schema、3 个任务、重复次数与限额；评测参考单独保存、不进入模型请求 | [protocol](../experiments/research_data_quality/2026-09-22-prompt-protocol/protocol.json)、[评测参考](../experiments/research_data_quality/2026-09-22-prompt-protocol/evaluation-reference.json) |
| 抽取 A/B | 3 任务 × 2 prompt × 2 次重复，第二次反转顺序；12 次真实调用全部返回结构化结果 | [运行结果](../experiments/research_data_quality/2026-09-22-prompt-run-01/result.json) |
| 校验与复核 | 精确引用/说话人检查、财务值逐项比较，以及所有电话会记录的语义复核 | [机械检查](../experiments/research_data_quality/2026-09-22-prompt-run-01/mechanical-review.json)、[逐项语义复核](../experiments/research_data_quality/2026-09-22-prompt-run-01/semantic-review.json) |
| 消费对照 | 原 Step 5 的规则数据包前后对照已运行，但重跑受连接错误中断；详见第 6 节 | [首次运行](../experiments/research_data_quality/2026-09-22-consumer-deepseek-01/result.json)、[重跑](../experiments/research_data_quality/2026-09-22-consumer-deepseek-02/result.json) |

抽取模型为 `deepseek-flash`，提供方回报模型名相同；非思考模式、temperature=0，每次最多 6,000 输出 token，独立上下文，没有检索工具或自动修复重试。固定任务为一张 2026 Q2 10-Q 财务表、一组 Q4 电话会准备发言、一个完整 Q&A。未测试其他公司、全篇召回或新 10-K 样本。

## 4. 优化前后结果

| 检查项 | 基础 prompt | Claude 改写 prompt | 判断 |
| --- | --- | --- | --- |
| F1：Cloud 收入/营业利润，季度与半年累计 | 两次均 8/8 数值及主体、期间、单位匹配 | 两次均 8/8 匹配 | 数值没有额外提升；现有规则也已支持这 8 项 |
| F1：记录显式关联单位原文 | 0/16 条重复观测 | 16/16 条重复观测 | 单条记录的单位证据更完整；两组输入都有同一单位原文 |
| T1：CFO CapEx 波动三因素与指引关联 | 2/2 次保留 | 2/2 次保留 | 基础组已能做好，不计为新增收益 |
| T1：Cloud 增长记录显式关联供给限制 | 1/2 次 | 2/2 次 | 小样本中更稳定；基础组原话仍包含该条件，不是完全丢失 |
| T1：把 CFO 的年内爬坡表述写到 CEO 引用下 | 第一次出现一次 | 两次未出现 | 改写组减少了一次错误归属；尚不能推广为整体误提取率下降 |
| T2：为“2026 大体相似”单列 `60` / `40` 数值预测 | 两次均产生 2 条，虽在文字中承认非精确数 | 两次均未产生，保留在 2025 记录/限定/缺口中 | 减少过度量化，但未来指引也未形成独立可查询记录，存在取舍 |
| T2：“just over half” 结构化 | 两次均 `value=50`，原文和摘要保留“略高于” | 两次仍 `value=50`；一次关联正确限定，另一次关联了泛化背景句 | prompt 不足以解决精确值/下界的表达歧义 |

这些关联数量是输出后的诊断观察，不是独立预注册主评分。8 个财务目标的重复结果不等于 16 个独立样本。语义复核由本任务 Agent 对照来源完成，未盲评，也不是独立人工 Gold。

### 可直接查看的例子

**单位证据**：两组都抽到 `2026Q2 revenue = 24768 USD_millions`。改写组另外关联了 `block-000483-091e8f25` 的原文 `…(in millions):`，基础组仅引用数字所在行。见 [基础组 F1](../experiments/research_data_quality/2026-09-22-prompt-run-01/F1-control-1/output.json) 与 [改写组 F1](../experiments/research_data_quality/2026-09-22-prompt-run-01/F1-claude_adapted-1/output.json)。

**供给限制**：改写组将 `despite the tight supply environment we're operating in` 放入 Cloud 增长记录的 `qualifiers`。基础组第一次只在完整 quote 内保留，第二次也完成关联。见 [基础组 T1](../experiments/research_data_quality/2026-09-22-prompt-run-01/T1-control-1/output.json) 与 [改写组 T1](../experiments/research_data_quality/2026-09-22-prompt-run-01/T1-claude_adapted-1/output.json)。

**仍有缺口**：改写组第二次的 Cloud ML compute 记录依然是 `value: "50"`，`summary` 说明“just over half”，但 `qualifiers` 引用的是“过去评论过 ML compute 分配”的背景句。逐字引用完全真实，却不等于关联语义正确。见 [改写组 T2 第二次](../experiments/research_data_quality/2026-09-22-prompt-run-01/T2-claude_adapted-2/output.json)。

### 与当前规则路径相比

现有规则已经能提取财务值、两处 CapEx 指引及 CFO 三项波动条件，没有证据支持用 LLM 替换这些确定性能力。两份 prompt 都提取到了 `block-000154-7394a8ae` 的折旧/能源费用压力，而当前字面 Cloud/CapEx 选择器没有为该块生成记录；这是语义抽取相对窄规则的覆盖增益，**不是改写 prompt 独有的提升**。

现有读取器已经保留完整 Q&A；机器、长期资产等内容原本可读取，只是尚未类型化。不能把新生成记录说成从源中找回了此前不存在的内容。

## 5. 费用与技术方案调整

| 抽取组（各 6 次请求） | 输入 token | 输出 token | 估算 USD |
| --- | ---: | ---: | ---: |
| 基础 prompt | 29,538 | 6,636 | 0.0168246 |
| Claude 改写 prompt | 31,680 | 6,743 | 0.0175956 |
| 合计 | 61,218 | 13,379 | 0.0344202 |

改写组费用估算增加约 **4.6%**。统一按官方高峰、无缓存美元单价估算，缓存 token 不重复计费；实际账单可能不同。短期请求延迟受网络和缓存影响，不把本轮延迟差异当作 prompt 的性能收益。

具体建议如下，尚未自动进入默认研究流程：

1. **保留确定性数值抽取。** 表格/XBRL 已有单元格、期间及单位校验；prompt 用于它不能覆盖的语义任务。单位说明补读已落实到此次实验打包器，新增回归检查。
2. **补数值含义字段。** 建议引入 `value_relation = eq / approx / gt / gte / range / qualitative`，将 `50 + gt + just over half`、`40 + gte + could be` 与精确数区分；不允许下游单独读取 `value` 就视为精确事实。这是需验证的新契约，尚未实施。
3. **把事实状态与记录类型分开。** 增加明确的 actual / management_forecast / derived_estimate 身份，以及目标期间证据。当前两组的 Cloud 定性增长仍是 `statement`、`period=null`；FY2026 “大体相似”也需要独立定性指引身份。
4. **校验关系，不只校验引用。** 字符串属于原文不保证它支持当前 summary 或 qualifier 关系。增加同说话人/同主题检查、限定词类别与待复核状态；不通过时保留候选，不自动发布。
5. **计算交给确定性计算层。** 下游已出现拿到正确操作数仍算错或漏算的情况。收入同比、利润率、利润率变化应生成带公式和操作数的 ComputedFact，再供 Agent 解释。

下一轮应在未用于改写的其他季度/公司样本上比较；当前结果不足以证明全篇召回、跨公司泛化或最终研究质量已经提升。

## 6. Step 5 的实际状态

这部分测试的是 **此前 Step 1–4 规则生成的数据包**，没有将本次抽取 prompt 产物写入其中。因此它不能证明 Claude 改写 prompt 的端到端收益。

首轮按原计划执行 8 次：7 次返回可解析且引用校验通过的候选，1 次 A1-after 在 2,200 token 上限截断。所有费用已知，估算 USD 0.0372168。随后保持来源和 prompt 不变，把双方上限统一改成 3,500 token，在新目录完整重跑，见 [重跑协议](../experiments/research_data_quality/2026-09-22-consumer-replay-protocol.json)。

重跑前 3 次成功，第 4 次 A2-after 出现 `APIConnectionError`，没有响应或用量。执行器立即停止，未继续后四次。重跑已知估算 USD 0.0155514，另有一条未知费用请求；该请求本地预留 USD 0.0166125，预留不是账单或已知费用。后续收费运行需先核对此请求状态，不通过新建目录绕过未知费用保护。

当前所有运行合计 **24 次请求尝试，已知费用估算 USD 0.0871884，另 1 次费用未知**；原总估算预算为 USD 1。抽取实验完成 12/12；Step 5 两轮结果均不能记为完整验收通过。

已有回答显示：

- A2 首轮前后两组都能保留 CapEx 指引、限定、资产构成、ML compute 分母与缺失 Q2 电话会，尚无清晰正确性增益。
- 相同问题的输入 token 从 A1 的 10,038 增至 13,203，A2 从 4,153 增至 7,404；结构化记录确实增加了输入成本。
- A1 首轮 after 第二次将 `2826 / 13624` 写成约 `20.75%`，正确两位小数是 `20.74%`；另有回答遗漏营业利润同比百分比。正确记录并不能自动保证计算和任务完整性。
- 重跑 after 给出正确的两位小数结果，但四位小数写错：实际利润率分别为 `20.7428068…%`、`35.5862403…%`，变化为 `14.8434335…` 个百分点。不能将更长、更精细的模型数字当作更准确的证据。

完整回答、逐请求日志与来源均已保存。连接问题未解决前，本报告保持“抽取已完成、消费未完成”，不继续消耗 API，也不自动采纳任何新结果。
