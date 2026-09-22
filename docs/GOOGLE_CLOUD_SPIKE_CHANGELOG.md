# Google Cloud LLM comparison — 2026-09-13

- A0 human approval recorded with artifact hashes; inspector now shows approved. A1 independently implements controlled FY2025 revenue withholding and narrow Data-side source recovery: 9 rounds, 20 calls, one guard rejection then successful correction/recovery. Parent unchanged, recovered value and six calculations verified. A1 remains pending review. See bilingual `CLOUD_ANALYSIS_A1` documents.

- A0 added: real model-directed Analysis Agent reads the approved snapshot and requests deterministic calculations. One live run: 5 rounds, 19 tool calls, 6 cited annual facts, 6 verified comparisons, zero check errors. New `/analysis` inspector; analysis review remains pending. 70 tests passed. No document retrieval or Thesis; details in `CLOUD_ANALYSIS_A0.zh-CN.md` / `CLOUD_ANALYSIS_A0.md`.

- Human review update: user approved the seven facts and evidence in `run-9856300a8d74fa77`. Added an append-only decision pinned to its snapshot SHA; inspector displays approval only for that exact artifact. Original run/evaluation remain unchanged. Other runs and general capability are not automatically approved.
- 人工审核更新：用户确认本次 7 条数据及出处通过。独立记录审核时间、范围和快照 Hash；历史运行与评测不覆盖，其他版本不自动继承批准。

- Added one real source-only model extraction, preserved input/output and model identity, immutable replay, and separate candidate-reference evaluation.
- Preserved a validator false rejection, then corrected metric checking to accept equivalent evidence tables via source XBRL concepts; replayed the unchanged response without another model call.
- Added rule/LLM version selection, input inspection and evaluation summary to the same inspector. Failed/prepared runs do not replace usable candidates.
- Result: 7 records, 0 candidate-reference differences; 57 tests pass. Human review pending. This is not a generalization or autonomous-analysis result.
- See `GOOGLE_CLOUD_LLM_SPIKE.zh-CN.md` / `GOOGLE_CLOUD_LLM_SPIKE.md` for matching details, limitations and next proposed Spike.

# Google Cloud Spike v0.1 — 2026-09-13

- Added a source-only, deterministic extraction baseline for named offerings and six annual revenue/operating-income records.
- Added date-gated, snapshot-pinned retrieval with pagination, exact evidence lookup and recorded missing-data requests.
- Added a simulator with 15 recorded tool calls and an independent-run inspector at `/result?view=cloud-spike`.
- Added a source-reviewed Reference candidate; evaluation runs separately from extraction. Human approval is pending.
- Verified six spike tests and the existing suite (52 total). Browser inspection confirmed the FY2025 operating-income cell highlight.
- Corrected the conversational example: FY2025 Cloud operating income is 13,910 USD millions. Source-manifest filing date is 2026-02-05; prior examples used 2026-02-04 without verification.
- Limitations: one fixed filing, no LLM run, no autonomous research loop, no acquisition worker, no general semantic/document search. Comparatives represent the FY2025 filing's presentation. Original-layout excerpts retain English.
- Next: human source/UI review, then a same-scope LLM comparison and document retrieval fallback.
