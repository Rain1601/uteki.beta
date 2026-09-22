# Anchored feedback / 划线修改意见

## 中文

- 右侧：材料标题 → 各次运行/修订的分钟时间与短 ID、状态。支持版本状态过滤；历史与操作记录保留在右侧，中间不再重复展示待审核和历史列表。
- 选中文字 → 写修改意见 → 保存。保存同时写入划线及关联意见，保留原句、位置、文本 hash、快照 ID、意见版本。已有纯划线可补写意见，不做无损迁移以外的自动变更。
- 点击划线可编辑；删除划线同时撤回关联意见。修改记录保留。意见与标注使用版本检查，防止其他页面的编辑被覆盖。正文保持不变。
- 默认请求带入下次运行，可取消。意见是待核查的人工输入，不是证据或强制指令。
- 同版重跑：明确指定 rerun_from，即使原报告未采纳或引用失败，也可以把它作为待修订草稿及意见输入；绝不能因此将其当成已采纳年度基线。
- 跨材料分析：仍只继承同研究者/主题且时间合规的已采纳年度基线上的意见。
- build_context(..., rerun_from=ID) 返回独立 rerun_source；普通 context 不会自动混入未采纳意见。严格历史模式排除截止日期之后创作的报告/意见；今天修改旧材料使用显式 retrospective 模式，不宣称盲测。
- run_archive_revision 是显式的后端重跑入口：构建并冻结上下文、固定材料、执行同一研究者模式；run_mode 接受冻结上下文，每个阶段都收到同一份内容。要求逐条回应意见、重读证据，说明接受/部分接受/拒绝/仍未解决。
- 保存不调用模型。本轮没有付费请求；运行入口通过离线替身测试验证输入传递，不能据此证明模型会正确采用意见。旧脚本未传 context 时行为不变。
- 当前页面未增加一键付费重跑；后端重跑产物不自动采纳，也未自动发布回公司列表。执行和结果接入应另行明确操作，不因保存触发。
- 上下文及运行产物只新增、不覆盖。原有引用门槛和用量记录继续有效。测试不修改用户的真实报告、意见或采纳状态。

## English

- Right rail: material headings and compact timestamp/ID/status version rows, with status filtering. Revision and audit history remain in the rail; duplicate center lists are removed.
- Select text, write feedback, save atomically. Preserve quotation, offsets, text hash, snapshot ID and opinion versions. Existing bare underlines can receive notes without automatic migration or rewriting.
- Clicking an underline edits its note. Removing it withdraws the linked opinion with history retained. Annotation and opinion revision guards prevent stale edits. Original report text is unchanged.
- Carry-forward is requested by default and can be disabled. Feedback is unverified human input, never source evidence or a mandatory conclusion.
- Explicit same-report reruns may use an unadopted or citation-invalid report as a draft to repair, never as an adopted annual baseline.
- Cross-material inheritance still requires an eligible adopted annual baseline in the same researcher/scope.
- build_context(..., rerun_from=ID) captures a separate rerun_source. Ordinary contexts do not inherit unadopted feedback. Strict historical mode enforces authorship dates; revising past material today is explicitly retrospective, not a blind backtest.
- run_archive_revision explicitly prepares and freezes inputs, pins materials and executes the source researcher's mode. run_mode receives identical frozen context in every stage and instructs evidence-based accept/partial/reject/unresolved responses per opinion.
- Saving does not invoke a model. This delivery used offline doubles, not paid calls or demonstrated model-quality improvements. Legacy callers without context remain unchanged.
- No one-click paid-run UI or automatic publication of rerun outputs into the company archive was added. Rerun execution/publication requires an explicit workflow; outputs are never automatically adopted.
- Outputs are append-only. Existing evidence gates and cost records remain. Tests do not alter real user reports, opinions or adoption decisions.
