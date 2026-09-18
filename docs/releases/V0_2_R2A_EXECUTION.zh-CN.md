# v0.2 / R2-A 开发执行记录

日期：2026-09-18。状态：**工程准备已实现并验证；R2-A 尚未签收，v0.2 尚未发布。**

用户已授权 plan + 开发。当前批次服务于一个固定 M0：Alphabet FY2025 10-K 的可核验业务地图。六类 Agent、Analysis team 和持续 Watch / Review / Update 的长期边界保持在架构与路线图中；本轮实现来源、候选和公共调用契约。

## 当前任务状态

| 任务 | 实际结果 | 尚需完成 |
| --- | --- | --- |
| V2-01 输入清单 | 完成：[42 项输入与产物记录](V0_2_INPUTS.json)，包括旧资料缺口、来源、版本、字节数和 SHA | 无 |
| V2-02 完整来源 | 已取得、保存、校验新原文和披露图片，建立新身份 | 负责人核对来源 |
| V2-03 证据问题 | 第 90 段差异定位；全部引用核验；新候选保留审计链 | 负责人复核异常处置 |
| V2-04 人工试标 | 第 88–91 段原文和四项判断已整理成独立包 | 真实人工试用、纳入/排除示例和分歧记录；不能用 Agent 自评代替 |
| V2-05 公共契约 | 输入范围、输出结构、失败记录、版本及候选边界已实现；基线设计已登记 | G0 规则收敛、正式 runner 的来源隔离及设计冻结 |

V2-06～12 尚未完成。模型和费用上限未指定；没有产生真实模型 baseline、Gold 或投资信号。

## 实际产物

| 产物 | 路径 / 身份 |
| --- | --- |
| 新来源快照 | [`data/source_documents/alphabet_2025_10k/r2a-20260918-candidate/`](../../data/source_documents/alphabet_2025_10k/r2a-20260918-candidate/manifest.json)，`sec-0001652044-26-000018-candidate-a24107da17e93e3e` |
| 新法定结构索引 | [`indexes/r2a-20260918-candidate/`](../../data/source_documents/alphabet_2025_10k/indexes/r2a-20260918-candidate/manifest.json)，`didx-26736eb127c3d5e6` |
| G0 人工试标包 | [`data/evaluation/m0_r2a/2026-09-18-candidate/`](../../data/evaluation/m0_r2a/2026-09-18-candidate/REVIEW.zh-CN.md)，`m0-review-candidate-170b0ad71397e7ea` |
| 设计登记 | [V0_2_BASELINE_DESIGN.zh-CN.md](V0_2_BASELINE_DESIGN.zh-CN.md)，含输入范围、旧候选暴露和未确定预算 |
| 独立重放证据 | [V0_2_R2A_REPLAY.json](V0_2_R2A_REPLAY.json)；[可复用入口的重放记录](V0_2_R2A_REPLAY_PORTABLE.json) |

新审核包自带 `source_snapshot/`、`legacy_inputs/`、来源审计、新业务地图、claims、spans、精确摘录及待答问题。包内路径相对自身，可以复制到其他目录再验证。所有回答、审核人和审核时间为空；人工回答需记录为后续审核版本，不能改写这个准备包。

## 来源取得与旧版本比较

固定来源：[SEC 原申报文件](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm)，Accession `0001652044-26-000018`，申报日 `2026-02-05`。

直接 HTTP 获取曾返回 403，随后通过浏览器的文件下载取得完整 HTML；两幅申报图片通过同一页面的附件取得。获取时间记录为下载文件实际时间 `2026-09-18T05:57:24.683474+00:00`（上海时间 13:57:24）。原始文件 **2,616,863 字节**；压缩存储不改写原字节。

原文 inline XBRL 字段核对结果：`Alphabet Inc.`、CIK `0001652044`、`10-K`、FY `2025`、报告期 `December 31, 2025`。这些机器检查辅助来源核对，不代替人工签收。

| 对比 | 结果 |
| --- | --- |
| 旧 raw SHA-256 | `c2f6301004f35411a20611c14ff01d80a85c0bcbab6053c80d8cc7f6fc747161`，旧原文不可得 |
| 新 raw SHA-256 | `1fd461af43b3dce4b6c26d8234b16dfb36c19cdd95db0e1092fd480dd2db3fb0`，与旧值不同 |
| legacy 段落契约 | 1,311 段；SHA `001dc7f7c4b0c3224769711ceab27f97fb2b6cc6302d7ea863c45c74cc0a49ab`，与历史测试中的完整段落清单指纹一致 |
| 现代结构索引 | 4 Parts、23 Items、1,339 Blocks、185 Tables、2 Images、0 diagnostics |

由于旧原文缺失，不能逐字节解释新旧 raw 的所有差异。此处保存新快照，不恢复或冒用旧 raw 身份。

HTML 实际包含第三个图片引用：SEC Akamai 的 noscript tracking pixel。原文完整保留；按固定 SEC 主机/端点、查询格式、noscript 上下文与样式识别后，在 manifest 中明确记录排除原因与策略版本，不请求它。两幅披露图片均保存指纹；普通隐藏图片或内容图片不会被笼统忽略。

legacy 段落解析采用 `sec-visible-blocks-v1`；新索引显式采用 `sec-source-blocks-v0.1.5`。旧默认解析版本未被静默改动。两种序号体系用途不同，引用中仍用 legacy paragraph ordinal + text_hash。

## 第 90 段及引用审计

旧摘录为 `• platforms, ...`，重新取得的原文解析为 `• platforms , ...`，差异是逗号前的一个空格。

- 旧记录 hash 和新原文 hash 都为 `2e86b1ceb5f574619bc1b27515bb8ac52df965b71257bae7dd0834bdf5ce9cc4`。
- 旧摘录文本重算得到 `113296d3ee15d4cdb5ef858a780812ac2f8e7bafcd68608ae3cdd88d13e62cba`，所以问题在保存的摘录文本。
- 受影响定位为 `e-platforms`，关联 `spd-composition` / `spd-platforms`；旧文件与原审核来历均保留。

完整核验：**22/22 证据定位、65/65 英文精确引文**对应原文；旧摘录为 **20/21** 一致，新摘录的 **21/21** 段直接取自来源。新候选含 9 个业务节点、42 条 claims。以上只证明机械来源一致，不证明主张语义正确、经济性判断正确或没有遗漏。

## 开发内容

- `snapshots.py` / `prepare_m0_source.py`：新候选导入、完整来源与附件检查、历史指纹比较、拒绝覆盖、完成后才发布 manifest。
- `index_artifacts.py` / `build_document_index.py`：新版快照必须通过完整校验，附件使用实际相对路径；构建始终为 candidate，拒绝覆盖；可显式指定解析器。
- `prepare_m0_review.py`：旧资料审计、剥离继承的审核状态、独立来源包、机械重放校验；只更新文件 hash 无法掩盖伪造的人工答案或错误派生。
- Business Map 公共 Agent：实际 prompt 版本与完整 schema、请求/实际模型记录、章节或全文输入、输入指纹、来源范围验证、成功与失败原文记录。新提示 v0.2 只接受 explicit/unknown；当前没有已批准推导规则的传输契约。
- 离线测试入口加入这些独立回归；已有历史缺数据测试保留原有失败边界。

此次独立代码审阅发现并修复了：索引绕过新来源完整验证、模型没有收到完整嵌套输出契约，以及非有限数使失败记录无法作为有效 JSON 保存。新增回归覆盖相应负例。

公共 Agent 本身不读 benchmark 或人工审核文件，但这并不对任意注入适配器提供系统级隔离。正式 runner 的来源白名单、模型预算和完整日志持久化仍是 V2-05/V2-08 的后续工作。

## 验证与重放命令

在已安装锁定依赖的仓库中运行：

```bash
.venv/bin/python scripts/run_offline_checks.py
.venv/bin/python scripts/prepare_m0_review.py --verify data/evaluation/m0_r2a/2026-09-18-candidate
.venv/bin/python scripts/replay_m0_preparation.py --output /tmp/uteki-r2a-replay-new.json
```

重放输出路径必须不存在。第三条命令在临时目录重新导入来源、重建索引和待审包，比较每个文件字节；不会覆盖现有候选。

需要重新生成索引或待审包时，选择新的输出目录：

```bash
.venv/bin/python scripts/build_document_index.py \
  --snapshot data/source_documents/alphabet_2025_10k/r2a-20260918-candidate \
  --output /tmp/uteki-index-new-candidate \
  --parser-version sec-source-blocks-v0.1.5
.venv/bin/python scripts/prepare_m0_review.py \
  --snapshot data/source_documents/alphabet_2025_10k/r2a-20260918-candidate \
  --output /tmp/uteki-review-new-candidate
```

若需再次从官方来源导入，使用浏览器下载上面的固定 SEC HTML 及两幅同目录图片，再调用 `prepare_m0_source.py`，显式提供原文、每个 `--asset NAME=PATH`、旧 manifest、真实获取时间和新输出目录。`--expected-paragraph-contract` 可传入上表的历史完整段落契约。完整参数见脚本 `--help`。重新下载的 raw 字节可能变化；必须据实创建新的来源身份并比较，不能为迎合旧 SHA 修改原文。

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| 全部便携核心回归 | **241 Python + 7 JavaScript，全部通过** | 离线、无模型调用；不是旧完整集成回归 |
| 真实待审包 `--verify` | 通过 | 全部来源/证据/派生产物校验，人工答案仍为空 |
| 新目录逐字节重放 | 来源 5 文件、索引 4 文件、待审包 17 文件全部一致（含 manifest） | 同一已安装运行时，尚非另一台机器/操作系统 |
| 独立输入检查 | 重放期间对原仓库 data/ 和 benchmarks/ 的读取尝试为 0；禁止 socket 操作 | Python audit hook 用于检测本次重放的外部依赖，不是通用系统安全沙箱 |
| 旧输入保护 | 6 份旧输入与执行前及 Git HEAD 完全一致 | 旧第 90 段坏摘录继续由旧 smoke 报告 |
| 格式检查 | `git diff --check` 通过 | 不替代研究验收 |

旧 workbench 所需原公司名单、catalog、研究发布和历史 experiments 仍缺失。本轮不生成同名占位资料；原完整集成模式并未通过。新包能独立审阅，不代表整个旧主页已恢复。

## 下一项真实验收

负责人阅读试标包第 88–91 段，对业务/收入类别/具名产品的粒度给出判断，并确认未知、推导和异常处置规则。执行者按原话记录为新的审核版本，补纳入/排除实例；然后才能冻结 G0 并进入完整 Gold 的逐项复核与遗漏搜索。

目前没有任何已记录的人工试标回答。没有将本轮源码检查或机械重放计为人工签收，也没有把旧候选暴露后的试点称为盲测。
