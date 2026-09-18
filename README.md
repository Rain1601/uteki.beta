# Uteki Beta

An evaluation-driven AI investment research system.

Uteki starts from a research question and evidence, then builds the data and
automation needed to answer it. The first milestone is deliberately small:
make one capability measurable before making the agent larger.

Product planning: [long-term roadmap](docs/ROADMAP.zh-CN.md),
[agent responsibilities and investment workflow](docs/AGENT_SYSTEM_DESIGN.zh-CN.md),
[active v0.2 plan](docs/releases/V0_2_PLAN.zh-CN.md), and
[release acceptance record](docs/releases/ACCEPTANCE_TEMPLATE.zh-CN.md).
These plans preserve the active M0 scope and do not imply milestone acceptance.

Investment governance: [investment and evaluation charter](docs/INVESTMENT_EVALUATION_CHARTER.zh-CN.md)
and [quarterly review template](docs/INVESTMENT_REVIEW_TEMPLATE.zh-CN.md).
Review quarterly, attribute annually, and assess the strategy over rolling 3–5
year windows. Research quality, position decisions, and returns are separate.
System-origin, manual, and unclassified positions require quantity-level attribution
and distinct reporting; manual tagging does not prove system performance.
Account parameters and benchmarks remain to be frozen. These documents do not
enable trading, implement position tagging, or expand M0.

The first v0.2 development batch now includes a newly acquired complete SEC
filing, a verified candidate index, and a portable G0 review package. See the
[R2-A execution record](docs/releases/V0_2_R2A_EXECUTION.zh-CN.md) and
[human review packet](data/evaluation/m0_r2a/2026-09-18-candidate/REVIEW.zh-CN.md).
Validate that package without network or model calls:

```bash
.venv/bin/python scripts/prepare_m0_review.py --verify data/evaluation/m0_r2a/2026-09-18-candidate
```

This package carries its own original source and legacy inputs. It is a new
candidate pending human review; it does not restore the old populated workbench
or complete the M0 evaluation gates.

## Research workbench

The local workbench now opens on an attention dashboard: pending reports,
recorded research updates from the last seven days, priority companies and
the remaining watchlist. Company-added dates are not available in the current
watchlist, so the dashboard explicitly marks that coverage gap. These are
research updates, not live market alerts. Daily viewed marks remain local to
the browser and do not approve reports.

Navigation: **Home → Companies → Company research → Reports**. Company pages
prioritize reading and editing analysis; source materials, document indexes
and structured business/financial data provide supporting evidence. Human
and agent edits retain separate revisions and do not overwrite or automatically
adopt the original report.

```bash
uv sync --locked --extra analysis
.venv/bin/python scripts/run_offline_checks.py
.venv/bin/python scripts/smoke_research_workflow.py
.venv/bin/python scripts/check_workspace.py
```

Start with [local setup and data recovery](docs/LOCAL_DEVELOPMENT.md) and
[the offline test boundary](docs/OFFLINE_TESTS.md). Python 3.11+, Node.js 20+
and macOS/Linux are required for these checks. The analysis extra is needed
for the offline SDK/fake-model tests; no model calls or credentials are used.
The workspace check exits with code 2 when required data is missing. After
restoring the inputs, launch the workbench:

```bash
PYTHONPATH=src:. .venv/bin/python -m apps.review_workbench.app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Startup now checks required inputs before
creating review state or starting the server. Use `--check` for a read-only
preflight. Full local regression remains available with
`.venv/bin/python scripts/run_offline_checks.py --integration`.
This code update does not publish the local source library or recorded
experiments. The full offline regression suite and populated workbench require
those local datasets; a fresh clone is not a preloaded research workspace.
Credentials, personal review state, run budgets, generated translations/exports
and temporary files also stay local. Research coverage and
review status remain explicit; this interface does not imply milestone
acceptance or completed coverage of every watchlist company.

## End state

1. **Research Outcome** — a defensible thesis, drivers, evidence, risks,
   variant perception, trackers, and falsification conditions.
2. **Research Data Infrastructure** — traceable filings, calls, news, industry
   data, claims, metrics, evidence, events, relationships, and timelines.
3. **Evaluation & Experiment System** — versioned benchmarks, baselines,
   metrics, error analysis, and experiment logs.
4. **AI Research Agent** — observable automation of the validated research
   loop, with humans retaining final judgment.
5. **Methodology** — a transferable way to define questions, manage evidence,
   evaluate systems, and update theses.

## Current milestone: M0

> Know exactly how weak the first baseline is.

M0 proves the minimum loop:

```text
fixed benchmark -> baseline predictions -> deterministic scoring
                -> error analysis -> hypothesis -> next experiment
```

The active boundary and five acceptance gates are defined in English and
Chinese in [`docs/M0_SCOPE.md`](docs/M0_SCOPE.md) and
[`docs/M0_SCOPE.zh-CN.md`](docs/M0_SCOPE.zh-CN.md). In short: Alphabet's latest
10-K, one decision-useful Company Business Map, and one complete evaluation
loop.

The modular-monolith boundaries and dependency rules are defined in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/ARCHITECTURE.zh-CN.md`](docs/ARCHITECTURE.zh-CN.md).

Earlier development referenced approved M1 and Data Agent / Analysis Agent
handoff documents, but those files and their English companions are not included
in this checkout. See the [missing-document inventory](docs/LOCAL_DEVELOPMENT.md)
before relying on them for implementation. M1 remains a later milestone.

The included metric-extraction fixture predates the current M0 definition. It
is only a technical evaluator check and is not the active benchmark or a claim
of system quality. The Alphabet Business Map remains a reviewed candidate.

### Spike D0: Document Navigator

D0 adds a parallel, source-faithful index for the frozen Alphabet FY2025 10-K:

```text
SEC HTML → Source Blocks → Document → Part → Item
```

It deliberately uses no LLM and does not infer hierarchy inside an Item.
Tables, source anchors, page markers, style signatures, and the filing's two
images remain inspectable in the populated local workspace. Its immutable index lives under
`data/source_documents/alphabet_2025_10k/indexes/v0.1/`; its reviewed
`v0.1-candidate` predecessor supplies provenance. These local index artifacts
are not included in a fresh clone.

### Data Agent handoff candidate

The separately provisioned local-file `EvidenceBundle` lives under
`data/research_data/alphabet_2025_10k/v0.2-candidate/`. It publishes the
current Business Map, Claims, normalized FY2025 Metrics, exact Evidence Links,
and known Unknowns through `LocalResearchDataPort`. The earlier
`v0.1-candidate` remains unchanged for comparison. The current release is
still a candidate pending full human review and contains no Thesis or Analysis
Agent judgment.

## Run it

The following research commands require their original local datasets and
review records. They are not bootstrap commands for a fresh clone.
Google Cloud's source-only rule spike has an implementation entry point at
`PYTHONPATH=src .venv/bin/python scripts/run_cloud_spike.py`, then open
`http://127.0.0.1:8765/result?view=cloud-spike`.

The same inspector now supports the source-only LLM comparison and pinned run selection.
The minimal Analysis Agent has a separate `/analysis` view. The Cloud rule/LLM
spike and Analysis A0/A1 scope documents are missing from this checkout;
[local development notes](docs/LOCAL_DEVELOPMENT.md) record the missing files.
Candidate-reference matching
does not constitute human approval or a generalization claim.
Evaluate a completed run separately with
`PYTHONPATH=src .venv/bin/python scripts/evaluate_cloud_spike.py <run-directory>`.
This is a rule baseline pending human review, not an autonomous LLM extraction run.

Requires Python 3.11+. The only document parsing dependency is `lxml`.

```bash
PYTHONPATH=src python3 -m uteki_eval evaluate \
  --benchmark benchmarks/metric_extraction/v0.1/dataset.jsonl \
  --predictions benchmarks/metric_extraction/v0.1/baseline_predictions.jsonl

PYTHONPATH=src python3 -m unittest discover -s tests -v

PYTHONPATH=src python3 scripts/build_document_index.py

PYTHONPATH=src python3 scripts/build_research_data_bundle.py \
  --generated-at 2026-09-13T01:34:55+08:00
```

Preview and review the current M0 pilot locally:

```bash
PYTHONPATH=src:. python3 apps/review_workbench/app.py
```

Then open `http://127.0.0.1:8765/result` for the Data Agent structured-data
Inspector or `http://127.0.0.1:8765/document-index` for the read-only D0
Inspector. `/result` reads the current published `EvidenceBundle`; Business
Map is one visualization of that data, not a Benchmark or Analysis Agent
result. The Document Index is frozen independently from both.

The evaluator reports exact-match accuracy, coverage, and an error manifest.
Its exit code is non-zero when input contracts are invalid, not when a model
scores poorly.

## Repository map

```text
benchmarks/       Versioned questions, ground truth, and baseline outputs
docs/             Project constitution, evolution, and experiment protocol
experiments/      Immutable experiment records (one directory per run)
src/uteki_eval/   Small evaluation kernel
src/uteki/        Research domain and SEC document infrastructure
tests/            Contract and metric tests
```

## Next gate

Complete the prepared G0 pilot with actual human research decisions, then
freeze the source policy, inclusion/exclusion rules, ambiguity policy and
review rubric. Public-contract and source-preparation development is in
progress; human Gold, paid baseline execution and release acceptance remain
pending. The [baseline design](docs/releases/V0_2_BASELINE_DESIGN.zh-CN.md)
records current exposure, input-scope differences and the unset model budget.
