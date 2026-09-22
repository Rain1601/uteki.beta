# Google Cloud 数据读取 Spike v0.1

状态：规则基线候选，人工验收待完成。中文为规范，英文配套。

范围：只读取冻结的 Alphabet FY2025 10-K 及其 Document Index。提取 Google Cloud 的具名 offerings，以及该文件列出的 FY2023—FY2025 收入和营业利润（USD millions）。产品组成表示披露的 offerings，不推断组织架构或穷尽产品目录。

方法：通过 Part I Item 1、Part II Item 8 的索引范围选择输入；句式规则提取 offerings；表格规则按指标分组、行标签、合并列表头确定数值。逐个核对原始 HTML 的 Inline XBRL scale、USD unit、年度 context 和 Cloud 主体。歧义或缺失时报错。本轮不调用 LLM，model/prompt 为 null，不构成 LLM 提取能力验证。

来源与时间：固定来源 SHA，校验索引文件 Hash。available_at 沿用来源清单的提交日 2026-02-05，仅日期精度；不声称是这些数字最早公开时间。比较年度数据均是本次文件的披露版本，不能用于模拟 FY2023 当时已知信息。原始运行时间、代码 Hash、索引 ID、节点 ID 和事实快照均保留。

验收：7 条数据（1 条组成、6 条指标）逐条对照 source-reviewed Reference candidate；人工确认后才可称 Gold。检查主体、期间、单位、数值和证据定位。Reference 不被提取器和模拟客户端读取。固定源规则与 Reference 来自同一开发过程，匹配不代表泛化能力。

读取：manifest 只给覆盖目录；facts 支持字段、期间、分页；evidence 按 fact_id 精确下钻，包含表格行列及年度表头；request_missing 只记录请求，尚无自动采集器。每次调用保留参数及完整返回。空结果区分 not_extracted/unsupported，不宣称未披露。服务内部加载文件不等于把完整文件放进模型上下文。

可视化：/result?view=cloud-spike 为本轮独立运行视图，显示提取事实、原版式片段、读取轨迹和来源身份。该视图不替代原有全业务候选，也不生成 Thesis。

执行：PYTHONPATH=src .venv/bin/python scripts/run_cloud_spike.py。每次生成新的 run 目录，不覆盖旧快照。tests/unit/test_cloud_spike.py 在评测侧读取 Reference。

下一轮候选：人工审核本轮数据和交互；相同范围接入 LLM 提取对照；增加原文目录检索接口及错误注入验证。跨公司、10-Q、全量 Fact Store 和 Thesis 继续按独立 Spike 处理。
