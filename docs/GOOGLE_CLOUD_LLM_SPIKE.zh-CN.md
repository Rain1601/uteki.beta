# Google Cloud · LLM 对照 Spike

状态：候选，待人工审核。本文补充规则基线 v0.1，不替代其历史记录。

## 本轮解决的问题

验证“真实模型读取原文 → 结构化事实 → 可核验出处 → 独立对照”的窄闭环。仍只处理 Alphabet FY2025 10-K 中 Google Cloud 的具名 offerings、FY2023—FY2025 收入和营业利润，不生成 Thesis，不扩展公司。

## 输入和运行

1. 校验来源 SHA 和冻结索引。选择 Part I Item 1、Part II Item 8。
2. 在范围内按 Google Cloud 字面匹配，附带相邻 Block。共 38 个 Block；相关表格整张保留，附上原始 Inline XBRL 的指标、年度、单位及 scale。
3. 将固定 prompt 和来源包发送给模型。没有读取 Reference，也没有读取规则提取结果。请求大小 112,205 bytes；实际计费响应报告输入 28,575 tokens、输出 847 tokens。
4. 原配置请求模型 `deepseek-chat`，服务实际返回 `deepseek-flash`；两者均记录。只获得一次真实模型回答。
5. 输出不自动修正。核验主体、重复、引用、数值、年度表头、USD scale、年度 Cloud context 和财务指标。具名 offerings 检查引用包含关系；语义完整性仍需人工审核。
6. 核验通过才生成候选 Snapshot；在独立评测进程读取 Reference。Analysis 端依旧是固定工具调用模拟，不是自主模型循环。

## 本次结果与校验器修正

- 原模型运行：`run-bc134b0c276425b0`。模型回答保留在 `response.raw.json` 和 `output.json`。
- 最初校验器误拒绝有效的收入表：它只认分部表里的 `Revenues:` 标题。模型引用的是第 60 页收入分解表，而规则基线引用第 87 页分部表。两者均披露相同 Cloud 收入。
- 校验器 v0.2 改为核对源单元格的财务指标（Inline XBRL concept），不要求同一个表格模板。保留错误记录，补充替代收入表回归测试。
- 不重新调用模型、不改回答；按原请求字节一致性检查后，在新运行 `run-9856300a8d74fa77` 重放核验。记录 `replayed_from`、原模型调用时间、响应 SHA；本次重放新增模型调用为 0。
- 7 条结果与候选参考一致：1 条 offerings，6 条收入/营业利润；差异 0。来源核验通过。Reference 仍待人工审核，不是独立测试集，不能推导准确率或泛化能力。
- 更早的受限网络尝试 `run-9a2f4a8962ac698d` 失败且无模型回答；准备记录也保留，不计入模型评测。

## 页面与版本

入口：`/result?view=cloud-spike`。默认显示最新可用候选，失败或仅准备的运行不替代结果。可用 `run` 参数固定版本，页面可切换规则版/LLM 版。

保持左右对照与数字高亮。新增候选参考差异摘要、实际模型输入、运行元数据；读取模拟与模型提取明确区分。UI 中英文切换，申报原文仍为英文。

每次运行独立目录保存 input、request、原始 response、output、diagnostics、run，以及通过校验后产生的 snapshot 和 trace。密钥不复制进仓库，不记录到请求产物，仅用于供应商认证。旧运行不覆盖。

## 复现与验收

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --prepare-only
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --env-file /path/to/local.env
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --replay-run data/research_data/google_cloud_spike/run-bc134b0c276425b0
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_cloud_spike.py data/research_data/google_cloud_spike/run-9856300a8d74fa77
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/unit -q
```

本轮 57 项单元/回归测试通过。浏览器检查收入原表及单元格高亮。人工下一步：审核 7 条事实及出处，确认参考范围，而不是据页面效果自动批准数据。

## 已知限制及下一步

检索仍是固定章节内字面匹配，不保证材料召回完整；数字校验只支持此次表格布局和已知财务概念，不是通用财务解析器。只进行一次模型提取；没有稳定性、跨文件或独立留出集验证。

下一步建议仍聚焦 Google Cloud：让 Analysis Agent 自主调用当前读取工具，并验证“缺数据时回到来源检索、仍找不到则明确缺失”的一条路径。Thesis、其他公司和季度材料暂不并入本轮。
