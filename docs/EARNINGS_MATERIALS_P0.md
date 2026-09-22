# Earnings materials P0 / 业绩材料最小闭环

## Delivered / 本轮交付

- Original 18 SEC indexes unchanged. A separate earnings.json joins the inventory.
  原有 18 份财报不变，独立 earnings.json 补充两份材料，统一列表读取。
- Official call PDF: 25 pages, 282 blocks, 9 Q&A exchanges, speaker roles and page
  coordinates. Original-page renders support highlights; full PDF retained.
  保留原件、原页坐标、发言人和问答关联；不使用 OCR 或 LLM。
- Release: SEC Exhibit 99.1, 104 blocks and 15 intact tables. Original SGML envelope
  retained as source.original; enclosed HTML is a derived view.
  发布稿保留原始下载文件和解包 HTML，未更改旧 SEC 解析接口。
- Release v0.2 corrects an unnumbered-first-page edge case: paragraph page numbers
  are unknown rather than borrowed from a later footer. Exact DOM links remain.
  发布稿 v0.2 不再将后页页码误带到无页码首页；旧 v0.1 保留但被替代。
- Candidate materials only, not approved research or benchmark answers.
  候选材料不自动采纳为研究结论。

## Sources / 来源

Official event discovery:
https://abc.xyz/investor/events/event-details/2026/2025-Q4-Earnings-Call-2026-Dr_C033hS6/default.aspx

Official linked PDF:
https://s206.q4cdn.com/479360582/files/doc_events/2026/Feb/04/2025_Q4_Earnings_Transcript.pdf

Release:
https://www.sec.gov/Archives/edgar/data/1652044/000165204426000012/googexhibit991q42025.htm

Event HTML download returned 403; the official PDF succeeded. Source manifests
record acquisition time, URL, MIME and SHA separately from event/release date.
The event/release date is 2026-02-04. Transcript upload time is NOT independently
verified. Date-level research only, not a point-in-time blind backtest.

网页下载受阻，改取官方 PDF。活动时间、文字稿上传时间、下载时间不可混为一谈。
当前以公开标注的日期筛选，不能宣称已实现无泄漏的日内历史回测。

## Agent contract / 读取约定

`load_catalog(root)` joins materials without overwriting the filing catalog.
`pin_materials(root, cutoff, document_ids)` explicitly selects and pins indexes;
rejects unknown, unindexed or future-dated materials. Existing `ToolSession`
supports documents → outline → search → read across both source families.
The analysis runner accepts `material_manifest=pin_materials(...)`; omitting it
preserves the existing experiment defaults. New model runs must explicitly opt in.

财报使用 Part/Item；电话会使用发言/问答。管理层长篇发言按请求的段落数读取，
每段带发言人信息，不强行加载整篇演讲。命中回答后 read 补带完整问答，
保留原始 Block ID。只有实际 read 过的内容进入引用账本。预算不足显式报错，
不静默截断。当前为英文原文关键词检索，不是语义搜索，也不保证检索召回。

Management statements are source statements, not verified facts. Analysis must
distinguish disclosed outcomes, expectations and inference. Historical runs stay
pinned to their old manifests; they do not silently gain new materials.

管理层陈述的真实性与预期/事实区分属于分析层。旧实验不自动加入新材料。
本轮没有付费模型调用；工具冒烟验证不等于模型回答质量验证。

## Reproduce / 复现

```sh
PYTHONPATH=src:. .venv/bin/python scripts/ingest_earnings_q425.py --call /path/to/original.pdf --release /path/to/release.html
PYTHONPATH=src:. .venv/bin/python scripts/earnings_reader_spike.py --output experiments/document_reader/earnings-p0-new-run
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/unit -p 'test_earnings_materials.py' -v
```

Ingest refuses differing originals/indexes; changed parsers need new versions.
The smoke command creates a new run and never replaces historical logs.

## Remaining / 后续

- [ ] Human review of source paragraphs, all nine exchanges and release tables.
- [ ] P1: three model-based questions, filing-only vs filing + call + release;
  same question/model/configuration, citations and cost records.
- [ ] Evaluate source support, missing/counter evidence and incremental value.
- [ ] Verify a standalone Q4 presentation if available; do not fabricate one.
- [ ] After review: historical quarter backfill, peers and translations.

局限：确定性发言人识别目前仅验证此稿；文字稿上传时间不确定；原文维持英文，
界面控件中英双语；尚无本轮投资分析答案，也不自动生成投资建议。

## Validation / 验证记录

Latest retrieval smoke: experiments/document_reader/earnings-p0-v0.3. This records
29 actual tool calls across the pinned three-material set, not LLM answers.
Unit checks cover lossless PDF word coverage, 9 complete question/answer contexts,
bounded prepared-remark reads, table structure, DOM locators, source SHA, cutoff
rejection, route delivery and compatibility with the existing tools.

Browser checks: material-type filtering, Chinese/English controls, keyword search,
PDF p.14 highlight against the real question, release HTML/table rendering, and
390px narrow layout. Temporary viewport override reset after inspection.
