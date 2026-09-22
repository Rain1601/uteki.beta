# Step 2：季度、累计与时点

状态：已执行。新增 18 条结构化记录；原文读取能力此前已存在，不将旧年度抽取器不支持的范围计作错误。

| 来源 | 主体 | 指标 | 起始 | 截止/时点 | 类型 | USD millions |
| --- | --- | --- | --- | --- | --- | ---: |
| Q1 | alphabet | capex_cash_payments | 2025-01-01 | 2025-03-31 | quarter | 17,197 |
| Q1 | alphabet | capex_cash_payments | 2026-01-01 | 2026-03-31 | quarter | 35,674 |
| Q1 | google-cloud | operating_income | 2025-01-01 | 2025-03-31 | quarter | 2,177 |
| Q1 | google-cloud | operating_income | 2026-01-01 | 2026-03-31 | quarter | 6,598 |
| Q1 | google-cloud | remaining_performance_obligations | — | 2026-03-31 | instant | 462,300 |
| Q1 | google-cloud | revenue | 2025-01-01 | 2025-03-31 | quarter | 12,260 |
| Q1 | google-cloud | revenue | 2026-01-01 | 2026-03-31 | quarter | 20,028 |
| Q2 | alphabet | capex_cash_payments | 2025-01-01 | 2025-06-30 | ytd | 39,643 |
| Q2 | alphabet | capex_cash_payments | 2026-01-01 | 2026-06-30 | ytd | 80,598 |
| Q2 | google-cloud | operating_income | 2025-01-01 | 2025-06-30 | ytd | 5,003 |
| Q2 | google-cloud | operating_income | 2025-04-01 | 2025-06-30 | quarter | 2,826 |
| Q2 | google-cloud | operating_income | 2026-01-01 | 2026-06-30 | ytd | 15,412 |
| Q2 | google-cloud | operating_income | 2026-04-01 | 2026-06-30 | quarter | 8,814 |
| Q2 | google-cloud | remaining_performance_obligations | — | 2026-06-30 | instant | 513,900 |
| Q2 | google-cloud | revenue | 2025-01-01 | 2025-06-30 | ytd | 25,884 |
| Q2 | google-cloud | revenue | 2025-04-01 | 2025-06-30 | quarter | 13,624 |
| Q2 | google-cloud | revenue | 2026-01-01 | 2026-06-30 | ytd | 44,796 |
| Q2 | google-cloud | revenue | 2026-04-01 | 2026-06-30 | quarter | 24,768 |

Q1 的 quarter 同时标有 ytd alias；Q2 单季与 H1 使用不同期间。RPO 是期末履约义务余额，不是当期营收。

两项派生值采用同口径现金购买固定资产支出：

| 单季 | H1 − Q1（USD millions） | 派生值 |
| --- | --- | ---: |
| 2025 Q2 | 39,643 − 17,197 | 22,446 |
| 2026 Q2 | 80,598 − 35,674 | 44,924 |

保存公式、操作数 record IDs 和来源可用时间。现金流表括号表示现金流出；本指标保留 XBRL 支出金额为正，不将它错误转成负 CapEx。与管理层 CapEx 的定义不自动视为相同。

查询验证：收入/营业利润分别返回 matched；未支持的毛利返回 missing；在该份材料披露日前查询返回 missing。没有用“某期间存在一个指标”代替所有指标齐备。

[Q1 记录](q1-output.json) · [Q2 记录](q2-output.json) · [派生计算](calculations.json) · [缺口与时点检查](coverage-and-cutoff.json) · [相对 Step 0](diff-baseline.json)
