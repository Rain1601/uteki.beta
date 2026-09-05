# Evaluation Protocol v0.1

## Unit of evaluation

One benchmark row is one independently answerable research-data question. It
contains a stable identifier, task, source locator, expected value, unit, and
annotation metadata. Ground truth must be human-reviewed.

## Active task family

M0 evaluates disclosed business-structure extraction from Alphabet 10-Ks:
business nodes, entity types, relationships, supporting evidence, duplication,
and cross-year disclosure changes. The precise contract and gates live in the
bilingual M0 scope documents.

Metric extraction, claim extraction, and evidence retrieval remain future task
families. The existing synthetic metric fixture is a pre-M0 technical check,
not the active benchmark.

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
