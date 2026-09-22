# Alphabet FY2025 10-K · Document Index v0.1

## 状态 / Status

- **Frozen**
- 人工验收确认日期：2026-09-12
- 来源候选版本：`v0.1-candidate`
- Index ID：`didx-028173790917c679`

该目录是 D0 首个正式冻结索引。后续解析逻辑修正必须生成新版本，不得覆盖本目录。

## 本版解决的问题 / Problems addressed

- 将 SEC HTML 建成可审核的 `Document → Part → Item` 法定目录，而不是截断全文。
- 保留 DOM 定位、SEC Anchor、报告页码、样式签名、表格结构和图片引用。
- 每个法定节点均可返回同一份冻结 SEC HTML 核验。
- 修正 SEC 页脚页码归属方向，Item 节点与起始 Block 的报告页码保持一致。

## 已冻结能力 / Frozen capabilities

- 999 个 Source Blocks。
- 185 个结构化表格。
- 2 个本地图片 Asset；保留 MIME、SHA、尺寸、Alt 和原始 URL。
- 4 个 Part、23 个 Item，全部唯一映射到正文。
- 目录 Anchor 优先、正文标题模式确定性回退。
- 原始版式与结构化 Blocks 两种只读检查模式。
- 中英文 UI Chrome；申报原文保持英文。

## Schema 与 Parser

- `schema_version`: `document-index-v0.1`
- `parser_version`: `sec-source-blocks-v0.1.1`
- 原有 `Document`、`Paragraph` 与 `parse_sec_html()` 行为不变。

## 验证结果 / Validation

- Source SHA：`c2f6301004f35411a20611c14ff01d80a85c0bcbab6053c80d8cc7f6fc747161`。
- 4 个 Part、23 个 Item 均唯一映射，节点范围无越界，0 条解析诊断。
- 185 个表格与 2 张图片均有对应 Block/Asset。
- 相同输入重复生成相同索引产物。
- 正式版 `index.json`、`blocks.jsonl`、`assets.json` 与通过审核的候选版逐字节一致。
- 原有 1,311 个 Paragraph ordinal/hash 指纹保持不变。
- 42 条 Claim、65 条 Evidence Span 与 `/result` 页面回归通过。

## 明确不包含 / Explicitly excluded

- 本索引不是业务分析 Benchmark，也不代表业务提取正确性。
- 不包含 LLM、PageIndex、AMD、10-Q、10-K/A 或 Business Agent。
- 不推断 Item 内部标题层级。
- 不解释 Inline XBRL 财务语义，不进行图片 OCR 或视觉理解。

## 下一版本规则 / Next-version rule

任何 Source、Schema 或 Parser 行为变化都必须产生新的版本和 Index ID；本目录保持不可变。
