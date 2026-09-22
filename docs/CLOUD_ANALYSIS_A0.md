# Analysis Agent · A0

Status: implemented and live-tested; analysis output pending human review. This document matches the Chinese scope.

## Scope

Answer only how Google Cloud revenue and operating income changed across FY2023–FY2025, including annual figures, two year-over-year intervals and the two-year cumulative interval. No Thesis, causal attribution, forecasts, trading advice, quarterly material or document retrieval.

Data and Analysis Agents are separate. Input is the user-approved snapshot from `run-9856300a8d74fa77`; approval and snapshot SHA must match. Approval of data does not approve analysis.

## Implementation

`src/uteki/agents/cloud_analysis.py` implements a budget-limited model loop:

- Initial context contains only the question, tool descriptions and output constraints, not the full facts or reference answers.
- Each model response selects JSON actions for a local allowlisted dispatcher. No preset reading sequence and no new Agent framework.
- `manifest` returns coverage; `facts` retrieves by metric/period with pagination; `evidence` requires previously retrieved fact IDs.
- `compare` accepts two retrieved numeric facts with matching subject, metric and unit in chronological order. Code computes change and percentage growth, rounded to two decimals. Nonpositive bases do not yield conventional growth percentages.
- Final structured answers reference fact/calculation IDs. Publication requires both metrics, three annual values each, six comparisons and all supporting evidence. Extra undefined numeric fields are rejected.
- Chinese/English trend summaries are model-authored, not automatically semantically verified. Causal explanation is out of scope.
- Limits: 12 model rounds, 40 tool calls, 8 calls per round. No silent retries or automatic answer repair.

`request_missing` only records requests. `not_extracted` means missing from this snapshot, not absent from the filing. The Agent should return blocked when it cannot complete; no source-document lookup tool exists in A0.

## Observed live run

`analysis-a6a15b4ee5167df6`, requested model `deepseek-chat`; returned per-round model identities are recorded in rounds. Five rounds, 19 tool calls:

1. Read coverage.
2. Fetch six annual revenue/operating-income facts individually.
3. Fetch their six evidence records.
4. Request six comparisons.
5. Reference returned IDs and produce bilingual summaries.

This is the observed model-selected sequence, not a hardcoded execution order. The input snapshot is saved for auditing but was not sent wholesale to the model.

## Validation

A separate evaluator checks model-action/trace agreement, tool replay consistency, annual fact/evidence coverage, and recalculates changes. Result: six annual facts, six comparisons, zero errors. This is execution consistency checking, not generalization on an independent test set. Narrative remains pending human review.

70 unit/regression tests passed, including unseen-fact citations, unknown tools, missing-data statuses, unapproved input rejection, historical availability, budgets, invalid citations and nonpositive bases. The live run encountered no gaps; missing-data behavior is unit-tested only, not validated autonomous source retrieval.

## Inspector

Separate `/analysis?run=analysis-a6a15b4ee5167df6`, linked from the approved Data page:

- Annual values open original-layout evidence and highlight the source cell.
- Changes/growth open formulas, with links to both original inputs.
- Expand tool trace, model actions, initial model input and run/check records.
- Bilingual interface/summary; source text remains English. Analysis stays pending while Data remains approved.

Browser verification covered growth → calculation → original-input highlight.

## Execution and records

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_analysis.py --env-file /path/to/local.env
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_cloud_analysis.py experiments/cloud_analysis/analysis-a6a15b4ee5167df6
```

Each run gets a new folder with question/version, input snapshot/approval, per-round requests/responses, trace, calculations, answer, diagnostics and evaluation. Credentials are authentication-only and not saved. Local server listens only on 127.0.0.1.

Next: review this answer and interaction, then scope a separate missing-data source-retrieval Spike. Do not expand Thesis or company coverage yet.
