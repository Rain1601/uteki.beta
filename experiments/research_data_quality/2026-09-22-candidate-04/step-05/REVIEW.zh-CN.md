# Step 5：下游消费对照准备与阻塞

**状态：两组输入与执行器已准备；真实模型 A/B 未运行。** 当前进程没有可用的项目 API 配置，已经请求现有本地配置位置。未用人工编写或沿用的答案充当新模型结果。

| Case | 优化前字符数 | 加入完整结构化记录后 | 增幅 |
| --- | ---: | ---: | ---: |
| A1 | 24,943 | 34,443 | 38.1% |
| A2 | 10,574 | 20,775 | 96.5% |

两组保留完全相同的原文 blocks，唯一输入改动是增加结构化记录及定位映射。因此这轮准备工作已证实“完整 JSON + 全部原文”会增加输入体积；不能声称 token 或费用下降。字符不是 token。

计划为 2 个问题 × 2 种输入 × 2 次重复，共最多 8 次调用，每次最多 2,200 输出 token；沿用项目 AIHubMix / gpt-5.4-mini 适配器，单独 USD 1 估算预算，失败费用未知时停止。价格沿用已注明日期的项目快照，不是假称实时账单。

这是固定输入的一轮消费实验，不是自主检索或工具补读实验；不能据此报告补读次数下降。

[A1 优化前输入](A1/before-input.json) · [A1 优化后输入](A1/after-input.json)

[A2 优化前输入](A2/before-input.json) · [A2 优化后输入](A2/after-input.json)

```bash
.venv/bin/python scripts/run_research_data_consumer_comparison.py \
  --prepared experiments/research_data_quality/2026-09-22-candidate-04 \
  --output experiments/research_data_quality/consumer-NEW_RUN \
  --env-directory /path/to/private-config \
  --budget-usd 1
```

只读取既有私有配置中的 API key，不把 key 放进命令、请求快照或报告。待真实输出出现后另记录引用检查、语义复核、用量和波动；当前不填写质量提升百分比。
