# Annual narrative Single Agent v0.1

Status: executed; report generated but citation validation failed. Not adopted.
6 successful model requests; 17 tool calls; 43.62 seconds. Estimated uncached-list
cost: USD 0.10157475, not a provider bill. See run/costs.json for each request.
8 failed citation occurrences refer to 3 blocks present in the source index but
not actually read by the agent (911, 736, 837). No silent repair or rerun.
The original preflight.json records the historical preparation stage only.
review.html displays the actual output and marks unresolved citations.

Only Alphabet FY2025 10-K, index v0.1, available by 2026-02-05 is exposed.
No Q1/Q2, prior answer, edited reference prose or preferred business ranking enters
the agent context. The five reading sections are fixed; research questions and
reasoning within them are autonomous. This is not a historical blind evaluation.

Use the existing AIHubMix gpt-5.4-mini / OpenAI Agents SDK adapter, with tracing
disabled and store=False. Gateway policies still apply. No retry loop, automatic
adoption, model judge, or Team arm. Each successful or failed model request has
a cost ledger; estimates use the dated 2026-09-13 stored list price, not a bill.

Credentials were loaded from the git-ignored local .env into this run's process,
without executing the file as shell code or exposing its values. The runner itself
still reads process environment only. The following was the prepared command;
do not rerun into this completed immutable experiment directory:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_annual_report_spike.py --output experiments/analysis_comparison/annual-narrative-single-v0.1 --run-prepared
```

Review raw-report.json and result.json without rewriting model conclusions.
Mechanical checks cover read provenance, cited paragraphs and section structure;
they do not establish truth or semantic support. Only after an actual result exists
should a comparison view be generated beside the edited reference. Assess clarity,
business understanding, evidence support, counterevidence, and material limitations;
do not grade agreement with the edited reference as correctness.
