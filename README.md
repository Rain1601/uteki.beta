# Uteki Beta

An evaluation-driven AI investment research system.

Uteki starts from a research question and evidence, then builds the data and
automation needed to answer it. The first milestone is deliberately small:
make one capability measurable before making the agent larger.

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
uv sync
PYTHONPATH=src:. uv run python -m apps.review_workbench.app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Run offline checks with
`PYTHONPATH=src:. uv run python -m unittest discover -s tests -q`.
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

The approved M1 scope and the Data Agent / Analysis Agent handoff are defined
in [`docs/M1_10K_THESIS_SCOPE.zh-CN.md`](docs/M1_10K_THESIS_SCOPE.zh-CN.md) and
[`docs/DATA_ANALYSIS_AGENT_CONTRACT.zh-CN.md`](docs/DATA_ANALYSIS_AGENT_CONTRACT.zh-CN.md),
with matching English companions. M1 remains a later milestone; these
contracts do not expand the active M0 scope.

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
images remain inspectable. The approved immutable index lives under
`data/source_documents/alphabet_2025_10k/indexes/v0.1/`; its reviewed
`v0.1-candidate` predecessor remains available for provenance.

### Data Agent handoff candidate

The current local-file `EvidenceBundle` lives under
`data/research_data/alphabet_2025_10k/v0.2-candidate/`. It publishes the
current Business Map, Claims, normalized FY2025 Metrics, exact Evidence Links,
and known Unknowns through `LocalResearchDataPort`. The earlier
`v0.1-candidate` remains unchanged for comparison. The current release is
still a candidate pending full human review and contains no Thesis or Analysis
Agent judgment.

## Run it

Google Cloud's source-only rule spike is documented in
[中文 scope](docs/GOOGLE_CLOUD_SPIKE.zh-CN.md) and
[English scope](docs/GOOGLE_CLOUD_SPIKE.md). Run
`PYTHONPATH=src .venv/bin/python scripts/run_cloud_spike.py`, then open
`http://127.0.0.1:8765/result?view=cloud-spike`.

The same inspector now supports the source-only LLM comparison and pinned run selection.
The minimal Analysis Agent has a separate `/analysis` view: see
[Analysis A0 (中文)](docs/CLOUD_ANALYSIS_A0.zh-CN.md) /
[Analysis A0 (English)](docs/CLOUD_ANALYSIS_A0.md).
For the separate controlled-gap source-recovery experiment, see
[A1 (中文)](docs/CLOUD_ANALYSIS_A1.zh-CN.md) / [A1 (English)](docs/CLOUD_ANALYSIS_A1.md).
See [LLM Spike (中文)](docs/GOOGLE_CLOUD_LLM_SPIKE.zh-CN.md) /
[LLM Spike (English)](docs/GOOGLE_CLOUD_LLM_SPIKE.md). Candidate-reference matching
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

Enter implementation planning and complete G0: source representation, evidence
locator, inclusion and exclusion rules, minimum schema, ambiguity policy, and
review rubric. Test the contract manually on a small filing section before
implementation.
