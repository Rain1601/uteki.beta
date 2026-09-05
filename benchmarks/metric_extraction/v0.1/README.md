# Metric Extraction Benchmark v0.1

This directory is a synthetic contract fixture, not an Alphabet benchmark.

Each JSONL row requires:

- `id`: stable and unique;
- `task`: `metric_extraction`;
- `source`: document and locator;
- `question`: the extraction request;
- `expected`: `value`, `unit`, and `period`;
- `annotation`: annotator, reviewer, and notes.

Predictions use the same `id` and a `predicted` object. Values are compared
after conservative text normalization; unit and period must match exactly
after case/whitespace normalization. Duplicate or unknown identifiers are
contract errors.

