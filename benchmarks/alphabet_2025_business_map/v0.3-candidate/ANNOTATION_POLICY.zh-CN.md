# Alphabet FY2025 业务地图标注规则 · v0.3 Candidate

## 状态

本版本是候选标准答案，不是冻结 Benchmark。它落实了已确认的 SPD 双结构决策，但仍需要逐节点、逐 Claim 人工审核。

## 目标问题

系统能否从 Alphabet FY2025 10-K 中恢复文件披露的业务构成、上下级关系、业务内容和财务披露规模，同时不把业务本体与财务披露结构强行合并？

## 两种结构

- **业务结构**回答“公司实际提供哪些不同的商业活动”：Subscriptions、Platforms、Devices 分别作为 L2 节点；
- **财务披露结构**回答“10-K 如何汇总收入”：`Google subscriptions, platforms, and devices` 作为一个 L3 Revenue Line；
- 三个业务节点通过 `supports` 指向合并 Revenue Line，但 `supports` 不是父子关系；
- 不得把 $48.030B 分摊给三个业务节点，10-K 没有提供这种拆分。

## 最小节点原则

核心节点采用“最细的、具有经济意义且能被原文证明的披露单元”。对象必须被文件明确命名，或由文件明确列举且经人工裁决为独立商业活动，并至少满足一项：

1. 是报告分部；
2. 有单独财务披露；
3. 文件给予独立的业务或变现描述；
4. 是理解父业务构成所必需的稳定业务组。

产品、品牌、功能和披露示例默认是 `allowed mention`。不得推断 Alphabet 的真实内部组织架构。

## 分层

- `L0`：公司背景；
- `L1`：报告结构；
- `L2`：商业业务或 Offering Group；
- `L3`：单独披露的财务收入线；
- `L4`：产品、品牌、功能或披露示例，不作为核心评分节点。

本版本共有 15 个 Required 节点。`business_architecture` 评分 L0–L2；`financial_disclosure` 在此基础上另外评测 L3，但二者不得被解释为一棵纯粹的组织树。

## 判定标签

- `required`：应被系统提取并参与 Precision / Recall；
- `allowed`：允许作为补充信息出现，不奖励也不惩罚节点召回；
- `unsupported`：固定 10-K 无法证明的节点或关系。

所有 Required 节点、层级边、跨视图连接和财务数字都必须定位到固定 Source Snapshot。`derived` 只允许表达建模裁决，不得伪装成 10-K 的直接陈述。
