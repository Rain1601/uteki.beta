# Step 1：财务记录对照

状态：已执行，候选结果；相同六个年度数字，不更换来源或模型。

| 指标 | 财年 | 优化前（USD millions） | 优化后 | 数值变化 | 原文披露位置数 |
| --- | --- | ---: | ---: | --- | ---: |
| operating_income | FY2023 | 1,716 | 1,716 | 未变 | 1 |
| operating_income | FY2024 | 6,112 | 6,112 | 未变 | 1 |
| operating_income | FY2025 | 13,910 | 13,910 | 未变 | 1 |
| revenue | FY2023 | 33,088 | 33,088 | 未变 | 2 |
| revenue | FY2024 | 43,229 | 43,229 | 未变 | 2 |
| revenue | FY2025 | 58,705 | 58,705 | 未变 | 2 |

改动：直接解析 iXBRL 的期间、维度、币种、scale/sign，校验表头与原单元格；record ID 与 series key 分开。收入的两处等值披露保留两个 occurrence，不计为两份独立佐证。

六个数值均保持一致。收益是可验证的财务上下文及复用契约，并非修正了六个原本错误的金额；下游效果仍待实测。

[完整记录与原文定位](annual-output.json) · [逐项差异](diff-parent.json) · [当前旧规则重跑结果](../step-00/current-rule-output.json)
