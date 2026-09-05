# G0 契约——公司业务地图 v0.1

## 状态

根据 Alphabet 2025 年 10-K 的 Item 1 形成的 Pilot 契约。Baseline 和 Review Workbench 实际验证前，它不能成为 Benchmark v0.1。

## 最小有用对象

### BusinessMap

- `schema_version`
- `company_id`
- `document_id`
- `summary`
- `businesses[]`
- `relationships[]`
- `unknowns[]`
- `evidence[]`

### Business

- `id`：地图内的稳定标识；
- `name`：报告披露名称；
- `kind`：`company`、`reportable_segment`、`business` 或 `offering_group`；
- `description`：简洁的经济性描述；
- `products_services[]`：代表性内容，不要求穷尽；
- `customers[]`：仅记录文件披露的客户；
- `monetization[]`：明确陈述，或者清楚标记为推导的陈述；
- `importance_signals[]`：记录证据，不生成统一分数；
- `evidence_ids[]`；
- `review_status`：`candidate`、`accepted`、`edited`、`rejected` 或 `ambiguous`。

### Relationship

- `source_id`、`target_id`；
- `kind`：`reported_under`、`part_of` 或 `supports`；
- `description`；
- `evidence_ids[]`；
- `review_status`。

对于 `reported_under` 和 `part_of`，方向从子节点/source 指向父节点/target。`supports` 有方向，但不能暗示所有权。

### Evidence

- `id`；
- `document_id`；
- `section_path[]`；
- 规范化文档内的 `paragraph_ordinal`；
- 规范化段落文本的 `text_hash`；
- `source_url`；
- `support`：简洁解释这段证据支持什么。

原始文本保留在来源文件中，不复制进 Benchmark。章节路径是便于人工阅读的提示；全文段落序号和文本 Hash 共同构成机器定位，并用于发现来源或 Parser 变化。

### Unknown

- `id`；
- `question`；
- `materiality`；
- `related_business_ids[]`；
- `reason_unanswered`；
- 当披露缺口本身有定位时使用 `evidence_ids[]`。

## 纳入测试

只有四个问题全部回答“是”，才纳入 Candidate：

1. 文件是否明确命名或无歧义地描述了它？
2. 它是否实质性增强了对 Alphabet 做什么或如何赚钱的理解？
3. 审核者能否根据具体段落核验？
4. 它是否没有被另一个节点重复表示？

具名产品通常放入 `products_services`，而不是单独创建业务节点。只有文件赋予它独立经济角色，并且业务地图需要这个角色时，才提升为节点。

## 主张纪律

- `explicit`：文件直接陈述；
- `derived`：按照已批准的确定性规则得出；
- `unknown`：固定来源无法支持。

M0 只有在保存推导规则和全部证据时才允许 Derived Statement。Agent Confidence 永远不能把 Derived 或 Unknown 升级为事实。

## Pilot 结论

Item 1 Pilot 表明：一张小型地图可以表示 Alphabet、Google、Google Services、Google Cloud、Other Bets 以及少量具有独立经济意义的 Offering，而不需要为每个具名产品建立节点。它也表明，共享 AI 基础设施更适合通过 `supports` 关系表达，而不是被强行塞进单一所有权树。
