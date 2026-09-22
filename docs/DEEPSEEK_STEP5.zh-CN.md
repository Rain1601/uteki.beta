# Step 5：DeepSeek 接入与运行

2026-09-22：DeepSeek 配置已就绪、真实 API 已连通。抽取层 12 次对照完成；消费端首轮有输出截断，完整重跑发生连接错误，未知费用保护已停止后续请求。详见[真实对照报告](CLAUDE_EXTRACTION_PROMPT_REPORT.zh-CN.md)。默认产品研究流程未切换。

## 配置与执行

依赖使用项目现有 `analysis` extra（`openai-agents==0.22.2`），无需安装新的模型 SDK。已有环境可直接运行；新环境先安装项目的 `.[analysis]`。

在进程环境变量或指定目录的 `.env` 中配置 `DEEPSEEK_API_KEY`。仅加载被选中的服务商密钥，不执行 `.env` 内容，不将密钥写入实验产物。`.env` 应是权限为 `600` 的普通文件，支持引号与 `export DEEPSEEK_API_KEY=...`。环境变量优先；不用把密钥发送到聊天或提交到 Git。

以下为运行命令参考，替换配置目录；输出目录必须尚不存在。当前已有一条费用未知请求，恢复前先核对该请求状态，不通过新建目录绕过保护：

```bash
.venv/bin/python scripts/run_research_data_consumer_comparison.py \
  --prepared experiments/research_data_quality/2026-09-22-candidate-05 \
  --output experiments/research_data_quality/consumer-deepseek-01 \
  --provider deepseek \
  --model deepseek-flash \
  --max-output-tokens 3500 \
  --env-directory /path/to/private-config \
  --budget-usd 1
```

CLI 默认服务商为 `deepseek`、默认模型为 `deepseek-flash`。也支持显式指定 `deepseek-v4-pro`。保留 `--provider aihubmix`，此时默认模型为 `gpt-5.4-mini`；不同提供方的密钥独立加载。未有已核对价格的模型组合会在创建输出目录前拒绝执行，不静默替换旧模型名称。

## 官方接口与适配依据

以下文档于 2026-09-22 实际读取：

- [首次调用 API](https://api-docs.deepseek.com/zh-cn/)：OpenAI 格式基础地址 `https://api.deepseek.com`，调用 `/chat/completions`。
- [Chat Completions 参数](https://api-docs.deepseek.com/zh-cn/api/create-chat-completion)：当前模型名 `deepseek-flash`、`deepseek-v4-pro`；`thinking` 默认开启，支持显式关闭；返回 `finish_reason`、模型名与用量。
- [JSON Output](https://api-docs.deepseek.com/zh-cn/guides/json_mode)：使用 `response_format={"type":"json_object"}`，提示词明确要求 JSON 并提供结构示例。JSON 模式只保证语法，仍需检查空内容、截断和字段结构。
- [官方美元价格](https://api-docs.deepseek.com/quick_start/pricing)：按百万 token，高峰 Flash 输入 $0.30、输出 $1.20，Pro 输入 $1.32、输出 $3.96。缓存与空闲时段有折扣，本实验预算和用量估算统一不应用这些折扣，也不做人民币换算；实际费用以提供方账单为准。

适配复用现有 Agents SDK 与本地 `Answer` 契约。DeepSeek 请求改为 `json_object`，将同一输出 schema 写入系统提示词；返回后仍由 Runner/Pydantic 校验。移除该接口未列出的 `store` 参数。当前适配在固定版本 SDK 的 `_fetch_response` 转换边界实现，升级 SDK 时必须重跑 HTTP 契约测试。

本轮使用非思考、非流式模式。默认输出上限为 2,200 token；真实首轮发生截断后，在新目录以 `--max-output-tokens 3500` 对双方完整重跑，未修改 prompt。两组始终使用相同模型、提示词/schema、模式与限制。若之后测试思考模式，应创建新实验并完整重跑，不拼接得分。

## 对照与费用记录

- 沿用已冻结的 A1/A2 问题与优化前后材料，执行前验证文件 hash；原候选目录只读。
- 两个问题 × 前后两组 × 两次重复，最多 8 次请求。第二次反转前后顺序，每次使用独立上下文，不增加自动修复或重试请求。
- `consumer-comparison-v0.2` 新增 JSON 输出示例及 DeepSeek 适配；新目录记录共同提示词、实际系统提示词、schema、代码 hash、SDK 版本、请求与价格快照，不覆盖 Step 0–4 结果。
- 每次记录提供方报告的模型名、响应/请求 ID、结束原因、原始用量、缓存/推理 token 与估算费用。模型名是提供方报告值，不保证底层权重版本被固定。
- 缓存 token 已包含在输入 token 中，推理 token 已包含在输出 token 中，不重复计费。
- 无效 JSON、schema 不匹配、空内容、非正常结束均不算有效候选；错误引用独立标记。已有用量的失败回答仍记录费用。
- 缺失用量、网络/认证失败的未知费用会停止整轮；预算不足会在发请求前停止。1 美元为本地估算预算，不是提供方强制扣费上限。
- 最终 `result.json` 才是整轮完成状态；`manifest.json` 是运行开始时的不可变配置。CLI 在失败、不完整或预算停止时返回非零退出码。

## 验证与待完成项

离线测试经过真实 SDK/Runner，仅将 HTTP 替换为本地模拟响应，检查实际请求 JSON、前后顺序、上下文隔离、提示词存档一致性、schema 校验、截断、空响应、认证失败、未知用量、预算预留与 AIHubMix 兼容性；也覆盖密钥加载和两种模型的价格口径。

```bash
.venv/bin/python -m unittest \
  tests.unit.test_deepseek_consumer \
  tests.unit.test_call_costs \
  tests.unit.test_analysis_comparison \
  tests.unit.test_narrative_reliability \
  tests.unit.test_research_data_steps
```

真实连通已验证，离线模拟与真实产物分开保存。当前消费验证尚不完整；核对连接失败的请求状态后，再按预算与相同配置恢复验证。实际回答已显示计算和任务完整性问题，不能只以引用检查通过证明质量提升。
