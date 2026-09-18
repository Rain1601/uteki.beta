# 本地开发与资料恢复 / Local development and data recovery

## 当前交付状态

此仓库提供应用代码、测试、一个 v0.1 Business Map 候选及部分真实来源摘录。原开发环境的公司名单、完整材料、研究数据发布、报告实验和审核记录没有完整提交。2026-09-18 接手时，这些资料暂时无法取得。

新环境可以运行离线核心检查及一条真实候选证据的隔离流程演练。完整工作台及历史研究报告仍需恢复下列资料。离线检查通过不代表 M0 验收、完整年报核验、模型质量达标或历史人工审核已恢复。

## 从新检出仓库开始

要求 Python 3.11+、Node.js 20+，运行环境为 macOS 或 Linux。归档存储使用 POSIX 文件锁。

```bash
uv sync --locked --extra analysis
.venv/bin/python scripts/run_offline_checks.py
.venv/bin/python scripts/smoke_research_workflow.py
.venv/bin/python scripts/check_workspace.py
```

依赖安装可能联网；后三个命令不请求模型、不下载资料、不需要 API 密钥。测试和流程演练只向临时目录写审核状态。`analysis` 扩展用于离线假模型及报告契约测试；实际工作台解析依赖仍只有 `lxml`。

`check_workspace.py` 在资料缺失时返回 **2**，同时列出必需文件和可选功能缺口。这个结果是当前公开检出的预期状态。可用 `--json` 获取结构化清单，或 `--root /path/to/recovered-checkout` 只读检查另一份候选工作区。检查会核对研究发布清单里的文件指纹、材料索引指纹和原文整体指纹；它不替代真实页面验收。

资料恢复后启动：

```bash
PYTHONPATH=src:. .venv/bin/python -m apps.review_workbench.app --check
PYTHONPATH=src:. .venv/bin/python -m apps.review_workbench.app --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765/`。启动会先检查必需输入；缺失或损坏时在绑定端口、迁移或初始化审核库之前退出。`--check` 即使检查通过也不启动服务、不写审核状态。完整来源、索引和分析扩展的缺口会单独报告。

完整本地回归的命令和覆盖边界见 [OFFLINE_TESTS.md](OFFLINE_TESTS.md)。`scripts/run_offline_checks.py --integration` 保留原测试失败与跳过结果，不会用占位资料补齐历史实验。

## 待恢复文件

路径均相对仓库根目录。恢复已有文件时保留原字节、版本目录、清单和审核记录，不重新赋予 frozen/adopted 状态。

| 内容 | 路径 | 用途与恢复方式 |
| --- | --- | --- |
| 原公司名单 | `data/company_universe/v0.1-candidate/companies.json` | 首页和公司导航必需；从原环境恢复，沿用原公司集合 |
| 材料目录 | `data/document_library/alphabet/catalog.json`，以及可选 `earnings.json` | Alphabet 所有正式子页都会加载；目录中的相对路径须保持可解析 |
| 已发布研究数据 | `data/research_data/alphabet_2025_10k/v0.2-candidate/` | 业务图、指标和公司页面必需；恢复 `manifest.json`、`evidence_bundle.json`、`business_map.json` 及清单声明的全部文件，例如 `query.json` |
| 完整年报及图片 | `data/source_documents/alphabet_2025_10k/source.html.gz`、`assets/` | 原文阅读、索引重建及独立验证；解压后的 HTML 须匹配现有来源清单 SHA-256 |
| 版本化索引 | 上述来源目录的 `indexes/`，以及材料目录各条记录指向的 `index_folder` | 目录导航和精确证据链接；保持 `manifest.json`、`index.json`、`blocks.jsonl`、`assets.json` 及引用图片一致 |
| 候选与审核决定 | `benchmarks/alphabet_2025_business_map/v0.2-candidate/`、`v0.3-candidate/` | 后续研究数据构建需要对应候选及 `review_decisions.json`；已提交的 v0.1 不能代替这些版本 |
| 历史报告及读取轨迹 | `experiments/analysis_comparison/`、`experiments/document_reader/` 及相应 Cloud 实验目录 | 恢复原报告、成本、校验与精确引用；没有实验时允许空报告列表，但历史回归不能据此通过 |
| PDF 资料 | `data/reading_library/alphabet/download_manifest.json` 及声明 downloaded 的文件 | 可选阅读功能；保持清单中的相对文件路径 |
| 个人审核历史 | `data/research_archive/state.json` | 可选；只从可信原状态恢复。没有该文件可以开始新的空档案，但无法据此还原过去的修订、采纳或撤回 |

建议先将原工作区恢复到单独目录，用 `check_workspace.py --root ... --json` 检查和比对；再按文件清单补齐当前工作区中缺失的路径。若同一路径已有不同字节，先核对版本和来源，保留两份以待审查。凭证不属于资料恢复包，模型执行前另行配置。

恢复后依次确认：主页 → Alphabet 概览 → 材料目录及原文 → 业务图及引用 → 报告及历史。真实人工采纳仍由研究者执行；离线演练的模拟采纳不会被导入。

## 能重建什么，不能重建什么

- `build_alphabet_business_benchmark_v0_2.py` 可从已提交的 v0.1 候选生成后续候选文件，但不产生人工审核决定。
- `build_business_map_v03_candidate.py` 需要缺失的 v0.2 `review_decisions.json`。不能用空决定文件声称已还原原审核。
- `build_research_data_bundle.py` 需要 v0.3 候选和原 `indexes/v0.1/manifest.json`。当前公开文件不足以重建既有 v0.2 EvidenceBundle。
- `build_document_index.py` 需要完整、指纹一致的源 HTML 及图片。取得原始字节后可在**新的候选目录**重建索引；新构建不能冒充过去已审核的冻结版本。
- 公司名单、历史工具轨迹、模型输出和人的采纳意见不能从年报重新推导为原记录。资料找不回时，需要另行建立有明确来源的新研究版本。

## 已知证据完整性缺口

已提交摘录的第 **90** 段，其当前文本按项目 `sec.text_hash` 规则计算的指纹，与存储指纹不一致：

```text
stored:     2e86b1ceb5f574619bc1b27515bb8ac52df965b71257bae7dd0834bdf5ce9cc4
recomputed: 113296d3ee15d4cdb5ef858a780812ac2f8e7bafcd68608ae3cdd88d13e62cba
```

相关证据为 `e-platforms`，涉及 `spd-composition`、`spd-platforms`。尚未取得完整固定源文件，因此这次没有修改原文、摘录或指纹。恢复原资料后，应核对到底是文本、指纹还是版本混用问题，并通过新候选及复核解决。

默认 smoke 只验证明确选定的 `alphabet-definition → e-overview → paragraph 55`，并同时输出全集指纹缺口。检查全部候选链可运行：

```bash
.venv/bin/python scripts/smoke_research_workflow.py --strict-all
```

当前该命令因第 90 段问题返回 **1**；这个失败应保留。默认模式成功仅表示所选局部证据和临时存储的生命周期检查通过。

## 尚未随仓库发布的设计文档

旧 README 提及下列六组文档，每组均包含英文 `.md` 与中文 `.zh-CN.md` 两份。目前均未提供；应恢复原文件，再核对其批准状态和当前适用范围：

- `M1_10K_THESIS_SCOPE`
- `DATA_ANALYSIS_AGENT_CONTRACT`
- `GOOGLE_CLOUD_SPIKE`
- `CLOUD_ANALYSIS_A0`
- `CLOUD_ANALYSIS_A1`
- `GOOGLE_CLOUD_LLM_SPIKE`

旧 README 对 M1 与交接契约只直接链接了中文版本，因此共有十个失效链接。此清单记录缺失事实，不重建或代替原设计决定。
