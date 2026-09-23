# Data Agent 离线端到端验收

模型调用 0 次。使用显式脚本规划器、真实 QueryDataPort、DuckDB、正文读取、完成条件、证据包和报告；不能证明模型拆题或 Analysis Agent 推理质量。

| 用例 | 结果 |
| --- | --- |
| alphabet-mixed | retrieval_satisfied |
| acme-mixed | retrieval_satisfied |
| other-company | retrieval_satisfied |
| missing-income | limited |
| prior-period | retrieval_satisfied |
| missing-scope | rejected |
| cross-company-source | rejected |

Alphabet 混合用例：完整 Business 79/79 块和营业利润率查询。独立合成公司 Acme：3/3 块和 15.00%；Other：3/3 块和收入 800 USD；上一年度收入 90 USD。合成值由测试数据明确声明，不代表真实公司或抽取泛化。

缺资料用例：Other 没有营业利润；实际查询保留缺口、未获完成许可。脚本规划器重复查询后触发 no_progress_limit，尚未证明模型能够主动澄清；该限制在各轮 feedback 与 completion 中保留。

每例 report.md、原文报告及 execution/session/event-* 保存可核查产物；Alphabet 例沿用既有显式任务计划。合成 run_question 例使用脚本 draft_plan，计划 origin=scripted_fixture，与本文件和 verification.json 一致。

下一步：使用同一费用账本运行真实模型混合问题及缺资料问题；再增加另一家真实公司已审核数据源。
