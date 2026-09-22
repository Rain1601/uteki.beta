# Alphabet 假设验证 MVP / Hypothesis review

本轮由当前 Codex 会话完成研究，不调用 AIHubMix，不代表已运行产品 Single Agent / Team。状态：待人工审核，不自动采纳，不修改公司档案。

## 实验问题

根据 FY2025 10-K，Alphabet 未来 3–5 年最重要的价值驱动及风险是什么？随后公布的 2026 Q1、Q2 对这些判断分别带来什么证据？价格与内在价值不等同于经营表现。

## 顺序与边界

1. 年报阶段只开放 FY2025 10-K，阅读其包含的往年比较数据；保存并以 SHA256 冻结 answer.json。
2. Q1 阶段保留初始假设，只新增 Q1；冻结更新后才开放 Q2。
3. Q2 阶段逐项对照 H1–H3，并独立追踪 Q1 才产生的 N1；不追溯改写初始预测。

通过本实验读取器执行的 outline/search/read 均保存在各阶段 reads/。每份日志含真实调用参数和完整返回结果，不是事后编造的模拟轨迹。Codex 会话上下文和训练先验未隔离，日志也不代表完整内部思维链；报告提供的是可审核的理由、证据和计算过程。实际使用资料的日期边界只约束读取器，不是整个模型的知识截止日。

Research is authored by Codex in this conversation. It is a sequential retrospective demonstration, **not** an autonomous SDK run, blind backtest, independent evaluation, or proof of investment skill. Existing source provenance is inherited from the local library, not re-authenticated on SEC this run.

## 固定产物

- 每阶段 materials.json：材料名单、公开日期、源 SHA、索引版本。
- answer.json + frozen.json：不可覆盖的阶段结果和冻结哈希。
- evidence.json：实际读取块中的逐字引文、页码、DOM 路径。
- reads/：目录、搜索和读取记录；搜索是确定性字面检索，不是向量检索。
- metrics.json：直接从被读取的表格单元格计算，保留基期、报告期和公式。
- validation.json：自动校验结果；不把来源可定位等同于推断正确。
- review.html：通过本地 8765 服务访问，原文链接可高亮对应块。

## 不做的事

不读取价格或盈利一致预期，不判断是否便宜，不自动改仓；不把季度收入同比与全年同比作为可直接等同的增长加速证据；不把 backlog 当收入，不把财报总体增长归因于 AI；不把本回溯结果当历史预测命中率。

## 费用

外部模型 API 调用：0。Codex 会话的精确 tokens 与美元费用无法通过此实验获得，因此留空，不记录为 0。工程工具调用日志不等于模型账单。

## 人工 review

先判断三个假设是否值得研究、是否真正可反驳；再检查引用与算术；最后检查后续结论是否遵守初始判据、是否过度解释或遗漏相反证据。不得因为结论符合个人偏好就采纳。

## 下一步（尚未实施）

用户审核本轮输出，修订实验协议后再用真实 Single Agent 在同样材料和输出规则下复现；比较遗漏、证据支持、口径错误与成本。然后补充电话会、外部竞争证据及截至节点的历史价格/估值情景。任何后续修订创建新版本，保留本次初始记录。
