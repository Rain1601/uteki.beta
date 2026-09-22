# Research workspace / 企业研究档案 · Change log

## 2026-09-14 · v1.1 researcher streams / 研究者独立演进

- Independent adoption slots and context identity; atomic confirmed replacement, rejection/reconsideration, immutable text revisions and audit diffs.
- 按研究者/主题过滤，每份主材料一行；候选与历史折叠。生效报告可直接派生修订，不先撤销生效。
- Migration preview, byte-exact backup, idempotent schema upgrade; unknown team identities are not guessed.
- 不修改原实验、不自动采纳、不新增模型调用。上下文接口已隔离，真实模型继承与意见语义审核仍未接入。
- Rules and limitations: RESEARCH_WORKSPACE_V1.1.md / RESEARCH_WORKSPACE_V1.1.zh-CN.md.

## 2026-09-13 · semantic citation presentation / 内容式引用

- 用可点击的已有引用摘录替换“出处 1”与无语义 ID，材料标签区分 2025 10-K、2026 Q2 10-Q 等。
- Drawer captions use the document name and excerpt; original source links and highlights remain unchanged.
- 未知材料/无图片文字/长摘录明确标记，不新增数值或生成结论；引用失败仍保持失败状态。

## 2026-09-13 · visual refinement / 样式迭代

- Apply user-supplied frontend-design skill; persist local skill and project working agreement.
- 冷白/蓝灰研究工作台：紧凑版本栏、正文阅读尺度、简化出处链接、说明折叠、关键警告保留。
- Company-data palette and typography aligned; companies list and state/data contracts unchanged.
- 中英文、窄屏、键盘焦点、减少动态效果及原文高亮检查；本轮无模型调用。

## 2026-09-13 · v1.0 foundations / 基础交付

- Confirmed bilingual specification: `RESEARCH_WORKSPACE_V1.md` and `RESEARCH_WORKSPACE_V1.zh-CN.md`.
- 公司页新增研究档案/公司数据两个 Tab；公司列表和旧来源、结果、实验链接保留。
- Import four existing real analysis results as candidates, never adopted automatically. Historical primary documents are explicitly inferred and require user confirmation.
- 采纳唯一性、归档、软删除/恢复、人工派生修订与复核；状态和审计同文件原子写入，支持并发版本检查。
- Independent, versioned human opinions with explicit carry-forward and withdrawal. Source withdrawal flags descendants without rewriting historical inputs.
- 最近合格基线、受限按需历史读取与不可覆盖上下文清单；尚未接入模型执行，不把待审意见称为事实。
- Same-page source drawer, exact source-block highlighting, date-only labels where publication time is unknown.
- 回归：158 项离线测试通过；最后标题收敛后 13 项 UI/路由测试通过。浏览器核查了真实候选展示、来源抽屉及高亮。未用真实用户档案执行测试采纳；写入测试隔离在临时目录。
- No new paid calls, no changes to old model answers or source snapshots. The preferred v0.2 Single result still has one unread citation and cannot yet be adopted.

### Next / 下一阶段

1. Repair evidence in a new Single revision without overwriting the original.
2. 接入 Analysis Agent 的冻结上下文及人工意见逐轮重审，确认预算后做最小对照。
3. Stable hypothesis IDs and explicit evidence-based changes between snapshots; no fabricated historical baseline.
4. 按用户 UI review 继续整合公司数据与原文双栏；当前保留真实 Data Agent 结果入口，未为所有材料生成语义数据。
# 2026-09-15 — Researcher material rail & annual context v1.2

研究档案改为左侧 Agent/Team、右侧材料列表及报告；状态紧邻标题，不再占据独立空白列。年度前两年基线与季度/补充材料验证基线采用确定性选择，并保留时间与采纳门槛。未调用模型、未改写历史。详细双语合同见 [RESEARCH_CONTEXT_V1.2.md](RESEARCH_CONTEXT_V1.2.md)。
