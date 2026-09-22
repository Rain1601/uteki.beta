# 研究工作台数据同步（8765）

本仓库包含工作台代码、公司列表、原始材料、索引、结构化数据和研究报告状态。

- `data/research_archive/state.json`：报告快照、修订、批注、采纳与操作记录。
- `data/company_universe/`：公司列表。
- `data/source_documents/`、`data/document_library/`、`data/reading_library/`：原始材料、索引及阅读材料。
- `data/research_data/`、`experiments/`：结构化研究数据和报告来源结果。

## 另一台电脑启动

```sh
git clone https://github.com/Rain1601/uteki.beta.git
cd uteki.beta
python3 -m venv .venv
.venv/bin/python -m pip install -e .
PYTHONPATH=src .venv/bin/python -m apps.review_workbench.app --port 8765
```

打开 http://127.0.0.1:8765/ 。使用 Python 3.11 或更新版本。

## 换设备继续编辑

编辑前先停止该设备的工作台并 `git pull --ff-only`，再启动。编辑完成后停止工作台，检查 `git diff`，提交 `data/research_archive/state.json` 和本次产生的材料/结果，随后 push。

这是通过 Git 交换版本，不是实时共同编辑。两台设备不要同时修改同一份状态文件；若发生冲突，保留两边版本并人工核对修订记录，不要直接覆盖一方。新生成的结果文件如受忽略规则影响，应检查后明确加入提交。

首页已读标记和语言偏好目前保存在浏览器 localStorage，不随仓库同步。密钥、虚拟环境、日志、锁文件、本地备份和运行预算不提交。仓库公开，后续提交前检查新增内容是否适合公开。
