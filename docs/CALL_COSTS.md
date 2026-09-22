# Call cost records / 调用费用记录

The Single/Team comparison runner now records each non-streaming model request.
当前接入范围：Single/Team 对比运行器的非流式模型请求；并非仓库中所有旧调用入口均已迁移。

- `calls/<id>-start.json`: durable start event before the request / 请求前写入。
- `calls/<id>-end.json`: usage, UTC timestamps, latency, stage, requested model, provider, request/response IDs when supplied, and errors by type only / 成功、失败及取消均记录，不存 Key 或异常正文。
- `costs.json`: per-mode summary / 每组汇总。
- `cost-report.json`, `costs.html`: run-wide ledger and readable report / 整轮明细页面。

Prices are frozen in the run manifest. AIHubMix GPT-5.4 mini public pricing checked 2026-09-13: USD 0.75/M input and 4.5/M output, source https://aihubmix.com/model/gpt-5.4-mini . Cache discounts are unverified and not applied. Estimates are not invoices. Other provider/model combinations remain unpriced until a verified snapshot is added.

价格随实验冻结。缓存输入已包含在输入 Token 中，推理 Token 已包含在输出 Token 中，不重复计费。实际账单字段保留为空，需后续对账，不能用估算填充。未知费用请求单列，不当作免费请求。进程被强制退出时开始记录仍保留，可识别未完成调用。当前 AIHubMix 客户端关闭内部自动重试；若以后开启 SDK 内部重试，需要追加传输层记录，不能把一次模型调用等同一次 HTTP 尝试。

Historical backfill / 历史补录：

`PYTHONPATH=src:. .venv/bin/python scripts/report_call_costs.py <run-directory> --backfill`

No paid calls. Reads saved per-request usage only; no invented timestamps/IDs. Excludes unsaved probes or failures. Existing raw model outputs/manifests remain unchanged; reports are create-only.

测试：离线覆盖计价、缓存/推理不重复计费、成功、失败、取消；不为测试费用记录重新发起付费模型调用。
