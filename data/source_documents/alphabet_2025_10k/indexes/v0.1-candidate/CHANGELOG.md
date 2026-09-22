# Alphabet FY2025 10-K · Document Index v0.1-candidate

## 本版解决的问题 / Problems addressed

- 将 SEC HTML 建成可审核的 `Document → Part → Item` 法定目录，而不是暴力截断全文。
- 保留原始 DOM 定位、Anchor、报告页码、内联样式签名、表格结构和图片引用。
- 让每一个法定目录节点可以回到同一份冻结 SEC HTML 中核验。

## 新增能力 / New capabilities

- Source-faithful Blocks：段落、标题候选、表格、图片和页码标记。
- 目录 Anchor 优先、正文标题模式回退的确定性索引。
- 不一致、缺失、重复和范围异常的显式 diagnostics。
- 两张申报图片的本地不可变 Asset 快照；不做 OCR 或视觉解释。
- `/document-index` 只读检查页，支持原始版式与结构化 Blocks 切换。

## Schema 变化 / Schema changes

- 新增 `SourceBlock`、`DocumentNode`、`DocumentIndex`、表格单元格与 Asset 元数据。
- `schema_version`: `document-index-v0.1`
- `parser_version`: `sec-source-blocks-v0.1.1`
- 原有 `Document`、`Paragraph` 与 `parse_sec_html()` 保持不变。

## 已知限制 / Known limitations

- 仅验证 Alphabet FY2025 10-K，不代表已适配 10-Q 或 10-K/A。
- Item 内部标题只标记为 `heading_candidate`，不推断业务或语义层级。
- Inline XBRL 保留在原始 HTML 中，但不解释其财务语义。
- 图片仅保留文件与元数据，不做 OCR、图表理解或描述生成。
- 本版是 Index Candidate，不是 Benchmark，也不是正式冻结索引。

## 验证结果 / Validation

- Source SHA 与冻结清单一致：`c2f6301004f35411a20611c14ff01d80a85c0bcbab6053c80d8cc7f6fc747161`。
- 4 个 Part、23 个 Item 均唯一映射；节点范围无越界；当前 0 条解析诊断。
- 185 个表格与 2 张图片均有对应 Block/Asset。
- 相同输入重复生成的 `manifest.json`、`index.json`、`blocks.jsonl`、`assets.json` 字节一致。
- 原有 1,311 个 Paragraph 的 ordinal/hash 指纹保持不变；42 条 Claim、65 条 Evidence Span 回归通过。
- 第二轮检查修正了 SEC 页脚页码的归属方向；例如 Item 8 起始 Block 现在与目录一致标记为报告第 44 页。
- 2026-09-12 完成人工验收确认；相同索引产物已提升并冻结为 `v0.1`，本候选目录继续保留。

## 下一版候选问题 / Next candidates

- D1：用 AMD 作为 fixture 验证 Item 内同样式标题的语义层级问题。
- D2：让 Business Agent 只接收 `document_index_id + selected_node_ids`。
- 在 D0 Schema 稳定后分别设计 10-Q 索引与 10-K/A `amends` 覆盖关系。
- PageIndex 仅通过 Adapter 导入同一 `DocumentIndex` Schema。
