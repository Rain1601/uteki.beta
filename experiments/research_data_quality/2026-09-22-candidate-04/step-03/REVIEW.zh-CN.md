# Step 3：电话会结构化

状态：已执行。保持既有 PDF blocks、说话人和完整 Q&A，新增规则抽取。

| 类型 | 数量 | 含义 |
| --- | ---: | --- |
| ManagementStatement | 35 | 匹配 CapEx/Cloud 主题的管理层原话；不自动当成已验证事实 |
| Guidance | 2 | CEO/CFO 对同一年度 CapEx 区间的两处表述；不计为两个独立预测 |
| QAExchange | 5 | 与命中主题关联的完整既有问答；不是全场 9 组问答的全量语义抽取 |

两个区间均为 FY2026、USD 175–185 billion，保留说话人、发布日期、原话与原文位置。分析师的问题保持 analyst 身份，没有进入 ManagementStatement。

本步发现一个明确不足：CFO 指引的条件说明在两段之后。该说明虽然已作为独立管理层陈述保存，却没有随 Guidance 返回。Step 4 只修这个上下文关联问题。

[全部记录与原话](output.json) · [前后差异](diff-parent.json) · [相对 Step 0](diff-baseline.json)
