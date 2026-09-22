# Step 4：指引与限定说明关联

状态：已执行；原文、数值、speaker 和 Q&A 均未重写。

| 指引 | 原先返回 blocks | 调整后 | 条件链接 |
| --- | ---: | ---: | --- |
| CEO FY2026 CapEx | 1 | 1 | 没有在本地窗口内找到条件，不猜测 |
| CFO FY2026 CapEx | 1 | 3 | 0 → 1 |

现在随 CFO 指引返回的限定原文：

> Keep in mind that the availability of supply, pricing of components, and timing of cash payments can cause some variability in the reported CapEx number.

来源：`block-000153-938fcda2`，Anat Ashkenazi，原电话会第 13 页；与同一轮中的指引 block 151 建立引用关系。

实现为显式调用的局部读取规则：同一 speaker/turn，最多向后 3 段，遇到话题切换即停止；不修改通用阅读器的默认行为。

初次尝试把 CEO 后面的 AI 议程与概述带入，已保留在 [初次输出](../../2026-09-22-execution/step-04/output.json)。边界修正后 CEO 仍返回 1 段，CFO 返回含限定的 3 段。范围仍是该类局部语境，不声称解决所有远端附注或全篇条件遗漏。

[优化后记录](output.json) · [逐项前后对照](diff-parent.json) · [相对 Step 0](diff-baseline.json)
