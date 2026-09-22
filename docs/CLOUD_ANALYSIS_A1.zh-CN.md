# A1 · 受控缺失与原文补取

## 状态与目的

A0 分析 `analysis-a6a15b4ee5167df6` 已由用户确认通过。新增独立审核记录，绑定答案、输入、计算、轨迹、评测和运行文件 Hash；历史产物不改写。

A1 是新实验，仍待审核：验证缺少一个已知年度值时，Analysis Agent 是否能请求 Data 端补取，再使用有出处的数据完成原问题。不扩展公司、Thesis 或通用检索。

## 可验证的方法

从已审核父快照派生临时缺失快照：仅去掉 Google Cloud FY2025 收入及不再被其他事实使用的出处，不修改父快照。缺失快照有新 ID/Hash，不继承父快照的批准。模型不收到被隐藏的值，也不读取评测参考。

新增 `source_lookup(predicate, period)`：

1. 只在同一字段/期间经过 `facts` 精确查询、返回 `not_extracted` 后开放。
2. Data 端重新读取固定 SEC 原始 HTML 和冻结 Document Index，使用已有 source-only Cloud 规则提取器，在 Part I Item 1 / Part II Item 8 范围内提取。
3. 返回指定事实、原文位置、表格单元格、年份、单位验证信息。绑定同一来源 SHA；不从父快照复制答案。
4. 补取事实使用新 ID 和 `pending` 状态，加入本次实验的独立结果层。Analysis 必须读取其证据后才可在最终答案中引用。
5. 不支持的期间返回 `unsupported_scope`，不能据此声称整个文件没有披露；不会自动下载新材料。

这是固定公司/指标的确定性适配器，**不是一般意义的文档检索或新的 LLM 提取能力证明**。一次受控实验不能证明真实缺失的全面召回能力。

## 实际运行

`analysis-9373e1c4632a063d`：9 轮、20 次工具调用。

- 模型先按指标分页读取，发现 FY2025 收入不足。
- 第 6 步直接调用 source_lookup，因尚未精确查询该年份而被拒。
- 第 7 步按 revenue/FY2025 查询，收到 not_extracted；第 8 步再次调用 source_lookup 成功。
- Data 端从报告第 87 页分部表补取收入 58,705（百万美元）。父数据采用第 60 页另一张收入表，两者都是同一申报文件的有效出处。
- 模型引用新事实和出处，完成 6 次变化计算，并在 limitations 中明确补取数据待审核。

这是模型根据工具反馈纠正动作；没有删除拒绝记录或修改模型答案。

## 核验与限制

独立进程重放动作、校验缺失先于成功补取、核对父数据 Hash 不变，并在评测侧比较隐藏值与恢复值。6 条年度事实和 6 次变化计算核验通过。0 项评测错误不等于 0 次工具错误：有 1 次被拒的调用，页面单独显示。

测试覆盖缺失快照隔离、不得跳过确认缺失、原文重新提取、来源 SHA 不匹配拒绝、未知期间、审核批准不随文件变化转移，以及真实运行重放。77 项单元/回归测试通过。

没有进行真实世界的未知问题搜索、语义召回评估或跨文件验证。模型摘要仍由人工判断。

## 查看与复现

`/analysis?run=analysis-9373e1c4632a063d` 显示 A1 待审核、实验说明、被拒/成功次数及完整轨迹。点击补取的 FY2025 收入可见新出处；点击计算继续下钻。A0 仍可独立访问并显示审核通过。

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_analysis.py --gap --env-file /path/to/local.env
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_cloud_analysis.py experiments/cloud_analysis/analysis-9373e1c4632a063d
```

input_snapshot 是缺失输入；resolved_snapshot 是本轮补取后的实验结果。input_review 仅指父输入的批准，不批准这两个新产物。每轮请求/响应、工具错误及修正、出处和答案均独立保存。

下一步先审核 A1；如继续扩展，应单独设计真正的 Document Navigator 检索，而不是把这个固定规则适配器扩展描述成通用能力。
