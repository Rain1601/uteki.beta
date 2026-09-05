# Uteki Beta

An evaluation-driven AI investment research system.

Uteki starts from a research question and evidence, then builds the data and
automation needed to answer it. The first milestone is deliberately small:
make one capability measurable before making the agent larger.

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
[`docs/M0_SCOPE.zh-CN.md`](docs/M0_SCOPE.zh-CN.md). In short: three consecutive
Alphabet 10-K filings, one disclosed-business-structure task, and one complete
evaluation loop.

The included metric-extraction fixture predates the current M0 definition. It
is only a technical evaluator check and is not the active benchmark or a claim
of system quality. No Business Structure implementation has started.

## Run it

Requires Python 3.11+ and has no runtime dependencies.

```bash
PYTHONPATH=src python3 -m uteki_eval evaluate \
  --benchmark benchmarks/metric_extraction/v0.1/dataset.jsonl \
  --predictions benchmarks/metric_extraction/v0.1/baseline_predictions.jsonl

PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The evaluator reports exact-match accuracy, coverage, and an error manifest.
Its exit code is non-zero when input contracts are invalid, not when a model
scores poorly.

## Repository map

```text
benchmarks/       Versioned questions, ground truth, and baseline outputs
docs/             Project constitution, evolution, and experiment protocol
experiments/      Immutable experiment records (one directory per run)
src/uteki_eval/   Small evaluation kernel
tests/            Contract and metric tests
```

## Next gate

Review and freeze the bilingual M0 scope, then complete G0: filing years,
source representation, locator convention, annotation taxonomies, ambiguity
policy, and scoring rules. Do not implement the Business Structure task before
G0 is approved.
