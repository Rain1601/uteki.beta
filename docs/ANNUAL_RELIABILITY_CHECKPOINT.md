# Annual reliability checkpoint / 年度可靠性检查点

2026-09-16 Asia/Shanghai. Progress, not a 1.0 release.

## Delivered / 已交付

- Reusable bounded narrative runner, one repair maximum, shared estimated-cost
  reservations, safe local credentials, preserved raw stages and revision diff.
- Named five-section output, compact transport without modifying source blocks.
- Read-backed table arithmetic and a conservative percentage coverage gate.
- Read-only comparison at `/experiments/v1-reliability-review/review.html`.
- Pure hypothesis/revision contract; not yet integrated with model/archive/UI.

## Actual experiments / 实际实验

| Version | Initial citation/structure errors | Final errors | Repairs | Estimated USD |
|---|---:|---:|---:|---:|
| v0.2-a | 3 | 3 | 1 | 0.53946375 |
| v0.2-b | 0 | 0 | 0 | 0.16071525 |
| v0.3-a | 1 | 0 | 1 | 0.14663100 |
| v0.3-b | 3 | 0 | 1 | 0.18448800 |
| v0.4-a | 2 | 0 | 1 | 0.38849625 |
| v0.5-a | 22 | 1 | 1 | 0.36721350 |

Machine records are authoritative if a copied table differs. Total new estimated
cost: USD 1.78700775 of USD 5 approved. Actual billed cost unknown; cached tokens
are recorded but no undocumented discount is assumed.

These are tiny development samples, not proof of reliability or profitability.
The new percentage gate was added after v0.4; its historical replay does not
rewrite those original validation results. In v0.5 it caught two initial percentage
coverage gaps along with twenty citation errors. After the one permitted repair,
citations passed but an unverified 40.89% remained. The run was rejected, not adopted.
The v0.5 error counts include percentage errors, unlike the older citation/structure
counts. Full Python suite: 254 tests passed; no live provider calls in these tests.

## Known blockers / 已知缺口

v0.4 retained unsupported calculated percentages after tool errors. Matching a
read quote alone cannot catch this. The new gate catches missing calculation
coverage but cannot prove the metric/period meaning or check all other numbers.
The model also overstates business quality and moat certainty in places. No
report from this checkpoint is approved or automatically adopted.

The quarterly chain, atomic revision acceptance, narrative archive/UI integration,
valuation inputs, competitor comparison, job controls and full evaluation suite
remain outstanding. Do not mistake a contract-only preview for persisted workflow.

## Reproduction / 复现

From repository root:

```
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/unit -q
PYTHONPATH=src:. .venv/bin/python scripts/render_reliability_review.py
```

Rendering and unit tests are offline and make no provider calls. Paid runs use
`scripts/run_annual_report_spike.py` with the existing shared budget file and a
new output folder; never overwrite an old experiment to make it look repaired.
