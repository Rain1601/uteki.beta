# Data Agent 端到端验证结果

本轮完成代码职责重组后的离线工具验收与真实 DeepSeek 验证。完整混合问题和合成另一公司问题已满足取证条件；缺资料问题在一次规划说明修正后直接返回明确缺口。新 Analysis Agent 尚未实现，因此这里验收到证据报告，不包含完整投资研究结论。

## 真实模型结果

| 用例 / 运行 | 请求次数 | 结果与产物 |
| --- | --- | --- |
| 混合问题首次连接 `live-mixed-01` | 1 | `APIConnectionError`，未生成计划；保留未知费用。 |
| 完整 Business + Google Cloud 2025 数字 `live-mixed-02` | 10 | 模型拆成两个任务；先查询，再连续读取。正文 **79/79**，收入 **58,705,000,000 USD**、营业利润 **13,910,000,000 USD**、利润率 **23.69%**；引用和 SQL 齐全。[实际报告](live-mixed-02/live-mixed/session/report.md) · [完整原文](live-mixed-02/live-mixed/session/report-source-text.md) |
| 缺 2022 年数据首次 `live-missing-01` | 4 | 正确返回零行并保留收入/营业利润/计算缺口；模型随后无效搜索、重复查询，最终 `no_progress_limit`，未通过主动澄清验收。[保留失败报告](live-missing-01/live-missing/session/report.md) |
| 合成 Other 公司 `live-other-01` | 4 | 独立拆题，正文 **3/3**、收入 **800 USD**；仅引用 `other-annual`，未串用 Acme / Alphabet。[实际报告](live-other-01/live-other/session/report.md) |
| 缺 2022 年数据修正后 `live-missing-02` | 1 | `needs_clarification`：根据选定结构化数据覆盖说明缺少收入、营业利润，请求对应资料。未执行 SQL，未替换年份。[实际报告](live-missing-02/live-missing/session/report.md) |

以上真实运行使用 `deepseek-flash`，没有预写 TaskPlan 或参考答案供模型使用。合成公司的输入资料已明确标注为合成。

独立只读复核已完成：混合、首次缺资料、Other、修正后缺资料各层 manifest 的 260 / 116 / 104 / 6 项文件哈希分别匹配；请求与各自 prepared 的问题、来源范围和数据集固定值一致。混合 79 个要求正文块全部有实际读取回执；两项数值的来源、期间、计算输入 ID 与 Decimal 独立复算结果对应。Other 仅使用自身来源；首次缺资料的四条 SQL 均返回 0 行。不同版本的 prompt 各按自身 prepared 核对，没有用最后版本倒改旧运行。

## 发现并修复的问题

- CLI 的无效计划曾返回成功退出码；现在 `invalid_plan` 返回非零。
- 离线脚本提案曾被标为 `origin=model`；现在规划器必须明确声明 `model` 或 `scripted_fixture`，未知来源在调用前拒绝。旧 `offline-01` 保留，新 [offline-02](offline-02/README.md) 的脚本提案来源已核对。
- 重组后的 prepare 固定真实实现、独立提示词及产物写入模块的哈希，避免只记录旧兼容入口。
- 数值规划增加精确实体、指标、期间、取值类型和公式输入的覆盖检查说明；当前结构化数据缺失时请求澄清，不扩大到无法生成结构化记录的章节搜索。执行说明也明确导航不能挂到数值 requirement。

缺资料的最后一次成功验证的是**初始规划识别缺口**，没有证明执行中恢复或计划修订已经实现。混合 / Other 成功运行使用 `prepared-mixed-02` / `prepared-other-02` 中固定的修正前提示词；缺资料修正使用 `prepared-missing-03`。旧成功运行未在最后这版提示词下重新调用，不能把不同版本混成同一次全量模型验收。

## 离线检查

[七例实际工具结果](offline-02/README.md)覆盖完整 Alphabet Business + margin、独立合成公司、另一期间、缺营业利润、缺 scope、跨公司来源拒绝。使用预设规划器与真实正文读取、DuckDB、完成检查、证据包和报告，模型调用 0 次。缺营业利润用例保留缺口并禁止完成，最后因无进展停止。

目录重组后 `scripts/run_offline_checks.py --integration`：**661 项 Python、7 项 JavaScript 通过**。随后导入路径收尾通过 18 项定向检查；最后缺资料提示词修正通过 25 项相关检查。各检查范围重叠，不相加作为独立测试数量。未做浏览器视觉验收。

## 请求与费用记录

用户已明确批准同一历史账本累计最多 48 次。本轮实际新增 **20 次请求：19 次成功响应、1 次连接失败**；历史累计 **46 次：44 次成功响应、1 次超时、1 次连接失败**。没有继续消耗剩余 2 次。

成功响应不等于任务成功：首次缺资料的 4 次成功响应仍以未通过主动澄清验收结束。

同一 `task-query-canary-v1/budget.sqlite` 保留原费用。当前已知累计估算 **USD 0.1217448**；两次失败的预留合计 **USD 0.0381942** 仍为未知，不是确认扣费；实际账单金额未知。继续按用户选择的 `record_only` 记录，没有重建账本或把失败费用当作零。

原三例配置为 [mixed](live-mixed-config.json)、[missing](live-missing-config.json)、[other](live-other-config.json)；缺资料最后单次重试使用 [retry](live-missing-retry-config.json)。混合含连接失败累计 11 次，缺资料累计 5 次，Other 4 次，均未超过批准的逐例上限 12 / 5 / 5。

## 剩余边界与下一步

1. 当前新 Analysis Agent 消费证据包、生成研究判断的链路尚未实现；先定义一个最小分析输入/输出与引用要求，再实施和验收。
2. 另一家公司目前只有合成输入的查询/阅读验证；真实公司从原文解析到入库和查询的端到端泛化仍需显式资料与适配器。
3. 执行中修改计划、跨运行恢复、OCR 和网络补充取证仍未实现。原始文件缺失不等于公司未披露，候选数据不自动采纳。

离线复现使用新输出目录：

```sh
PYTHONPATH=src:. .venv/bin/python -m scripts.run_data_agent_e2e --output /tmp/uteki-e2e-new-run
```

真实运行均有固定配置、源码哈希、每轮输入/决策/工具返回、原文、证据包及费用。已运行目录不可覆盖；旧 prepared 在代码改变后不能复用执行。
