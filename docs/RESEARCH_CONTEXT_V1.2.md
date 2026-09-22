# Researcher materials & annual context v1.2 / 研究者材料与年度上下文

## 中文

- 研究档案左侧固定展示 Agent / Team；右侧只展示所选研究者与主题的分析材料、有效版本及历史。公司列表和公司数据页不改动。
- 每份材料仍只有一个生效报告。选择材料后阅读报告；采纳、拒绝、归档、人工修订和划线机制不变。
- 公司 10-K：默认加载同一研究者、同一主题下前两个财政年度的已采纳 10-K 分析。少一年就记录一年缺口，不用更早年份或季度报告补位。
- 10-Q、电话会、业绩发布、竞对材料：默认加载最近可用的本公司已采纳 10-K 分析，目标是验证假设。竞对 10-K 不是本公司年度基线。
- 核查输出应区分：支持、削弱、否定、证据不足。可提出新假设，但不能静默覆盖年度判断。年度基线和人工意见均不是真理，仍须查证。
- 仅采纳且通过原有资格规则的报告可以继承。材料公开时间、报告知识截止时间、严格模式的运行时间门槛继续生效。当前材料晚于截止时间或缺少公开日期时拒绝准备上下文。
- 若未来撤回任一年度基线，其依赖报告都会标记需要复核；冻结的运行输入保持原样。
- 新上下文使用 schema 1.2，完整答案仅置于 baselines，较早年报为按需目录。意见每次标记 pending review；不复制文件路径或完整材料索引到模型上下文。
- API：GET /api/research-archive/context?researcher=single-default&scope=company-drivers&material=材料ID&cutoff=YYYY-MM-DD。默认严格历史模式；mode=retrospective 明示允许今天解读旧材料，但仍限制材料知识时间。
- 兼容边界：不传 material 的旧接口保留 legacy-v1.1。新调用必须传 material，不能用旧接口声称已应用新规则。
- 实施范围：纯工程的上下文选择、冻结、回读与展示。尚未接到新的分析模型运行，没有模型费用；没有改写、采纳或重新运行历史报告。既有实验不会自动获得这一能力。
- 验证：覆盖前两年、多研究者、缺失年份、季度/电话会、竞对、时间边界、双基线人工意见、依赖撤回、HTTP 接口和只读历史。全量 216 项测试通过。

## English

- The fixed left rail selects an Agent / Team; the right lists only its scoped research materials, effective reports and history. Companies and company-data pages are unchanged.
- One effective report per material remains enforced. Adoption, rejection, archiving, human revisions and underlines retain their existing behavior.
- Company 10-K: preload adopted, eligible annual analyses from the exact previous two fiscal years, for the same researcher and scope. Explicitly report missing years; do not substitute older or quarterly reports.
- 10-Q, calls, earnings releases and competitor materials: preload the latest eligible adopted company 10-K analysis to test hypotheses. A competitor's 10-K is not the company's annual baseline.
- Expected judgments: supported, weakened, contradicted or insufficient evidence. New hypotheses are allowed but must not silently overwrite annual judgments. Neither prior analysis nor human opinion is established truth.
- Existing adoption, source publication, knowledge cutoff and strict run-time gates remain. Current materials with unknown or future publication dates are refused.
- Withdrawing either annual baseline flags dependent reports for review without rewriting frozen inputs.
- Schema 1.2 loads answer payloads once in baselines; older annual reports remain an on-demand directory. Opinions require review on every run. Internal file paths and full material indexes are not copied into context metadata.
- API: GET /api/research-archive/context?researcher=single-default&scope=company-drivers&material=MATERIAL_ID&cutoff=YYYY-MM-DD. Strict historical mode is default; mode=retrospective allows present-day analysis of old material while preserving knowledge cutoffs.
- Compatibility: requests without material retain legacy-v1.1. New callers must pass material to apply v1.2.
- Delivery is deterministic preparation, freezing, history reads and UI only, not a new model execution. No provider calls, cost, adoption or historical report rewrites. Existing experiments are not automatically integrated.
- Verification covers annual selection, researcher isolation, missing years, supplemental/competitor documents, date boundaries, both baselines' opinions, withdrawal propagation, HTTP routes and history. Full suite: 216 passing tests.
