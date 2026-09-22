# Single / Team pilot

OpenAI Agents SDK 0.22.2 orchestrates both modes. AIHubMix is accessed with AsyncOpenAI + OpenAIChatCompletionsModel at https://aihubmix.com/v1. The explicit model for this pilot is gpt-5.4-mini. No independent OpenAI API key is needed for this gateway; tracing to OpenAI is disabled and store=False is requested. Upstream gateway retention/routing remains governed by its policies, not these settings.

Single: analyst → answer. Team: analyst → reviewer → analyst revision. Each stage has an SDK-driven tool loop. Reviewer gets the question and draft, but no Single output. Single and Team run concurrently with separate contexts and evidence ledgers. Team roles execute sequentially. No handoff/MCP server is needed for this first fixed workflow.

Sources are pinned from multi-query-v0.2: only documents/index manifests are copied into the run; historical answers and checklists are not exposed to the model. Every factual claim must cite a read block and an exact quote. The mechanical check cannot establish entailment or completeness; human review remains required. Reviewer-stage citation checks separately test whether the reviewer itself read its evidence.

Budgets: 30 tool calls and 150k returned text characters per mode; max 60k characters per tool payload; 12 model turns / 180 seconds per stage; 4,000 output tokens per model request. Team has three stages, Single one, so this is not an equal-token-budget comparison. No dollar budget is implied. Cache/reasoning token details are retained as SDK usage. Failed runs retain completed stages, but incomplete-stage usage may be missing; do not mistake it for zero cost.

Actions are read-only. Secrets come from AIHUBMIX_API_KEY in the process environment, never CLI arguments or run snapshots. Model input snapshots, per-tool short operational reasons, returned blocks, stage outputs, usage, citation errors and failure statuses are stored locally. No private chain-of-thought logging is requested.

Run with the analysis optional dependency installed, and a local environment key:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_analysis_comparison.py --provider aihubmix --model gpt-5.4-mini --output experiments/analysis_comparison/NEW_RUN
PYTHONPATH=src:. .venv/bin/python scripts/render_analysis_comparison.py experiments/analysis_comparison/NEW_RUN
```

Each output directory is create-only. The gateway's actual upstream provider is not pinned or independently verified; do not infer strict model-provider reproducibility. The three-case pilot is not a statistical benchmark.
