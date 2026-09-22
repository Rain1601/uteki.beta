# Reading groups v0.1 / 阅读分组

Pure deterministic engineering; no LLM or business hierarchy inference.
纯工程规则，不调用 LLM、不推断业务层级。

Consecutive list items (including legacy bullet-prefixed paragraphs) are grouped with an immediately preceding colon-ended introduction and optional adjacent heading. Recognized page furniture can be traversed; Part/Item boundaries cannot. Ambiguous prose remains unchanged.
连续列表项（含旧版标记为 paragraph 的圆点条目）与紧邻的冒号引导段、可选标题组成阅读单元。跨已识别页眉页脚，但不跨 Part/Item；不确定的普通段落保持原样。

Original blocks, IDs, hashes and frozen indexes stay unchanged. Inspector renders compact lists. Reader expands a hit to complete list context; returned count may exceed the requested count and carries group metadata. This replaces count-only boundaries for recognized lists, not all prose.
原 Block、ID、Hash、冻结索引不变。页面紧凑显示列表；读取命中项时展开完整列表上下文，显式返回分组信息，数量可能超过请求值。尚不处理所有普通段落的语义边界，也没有大列表 token 分页。

`scripts/build_reading_groups.py` creates an immutable overlay under experiments/reading_groups/v0.1 with pinned source/index hashes and rules hash. Existing demo records are retained, not rewritten; new calls must create a new run after reader changes.
生成的阅读分组保存在独立版本目录，保留来源与规则版本。旧问答记录不改写；工具更新后新建运行。

Review fixture: FY2025 Competition, Blocks 110–122, contains the heading, introduction and all 11 items. UI review remains required. Derived overlays are candidates, not approved benchmarks.
验收样例：FY2025 Competition，110–122，包含标题、引导段和 11 项列表。阅读分组是候选产物，仍需人工检查。
