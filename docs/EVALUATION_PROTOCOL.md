# Evaluation Protocol v0.1

## Unit of evaluation

One benchmark row is one independently answerable research-data question. It
contains a stable identifier, task, source locator, expected value, unit, and
annotation metadata. Ground truth must be human-reviewed.

## First three task families

1. Metric extraction: exact value, period, unit, and source location.
2. Claim extraction: precision, recall, attribution, and evidence span.
3. Evidence retrieval: Recall@k and source/location agreement.

M0 implements only the metric-extraction scoring contract. The other task
families should reuse identifiers, provenance, versioning, and experiment logs.

## Benchmark lifecycle

- Freeze each released dataset directory; corrections create a new version.
- Keep the test set hidden from prompt or pipeline tuning when the corpus grows.
- Record who annotated an item and who reviewed it.
- Resolve ambiguity before scoring; do not tune normalization to excuse errors.
- Report results by slice (document, period, metric type), not only one average.

## Experiment rule

Every experiment begins by copying `experiments/TEMPLATE.md` into a new,
date-prefixed directory. Record the hypothesis before the change. Store the
exact command, code revision, benchmark version, aggregate metrics, individual
errors, cost/latency, conclusion, and next hypothesis.

