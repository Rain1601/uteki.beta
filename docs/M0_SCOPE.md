# M0 Scope — Alphabet Metric Extraction

## Outcome

Produce the first credible answer to a deliberately uncomfortable question:

> How well does the current Data Agent extract Alphabet metrics from primary
> source documents, where does it fail, and what should we test next?

M0 is complete only when the answer is supported by a reviewed dataset,
reproducible baseline, metrics, and individual error analysis.

## In scope

- Alphabet as the only company.
- Primary-source documents with stable locators.
- A small, representative set of financial and operating metrics.
- Human annotation and review instructions.
- Benchmark versioning and provenance.
- One simple migrated or reconstructed baseline.
- Exact-value, unit, period, source, coverage, cost, and latency evaluation.
- Manual review of every incorrect or missing result.
- One documented follow-up experiment based on observed errors.

## Out of scope

- Company discovery and screening.
- General company analysis or autonomous thesis generation.
- Portfolio sizing and portfolio management.
- Multiple companies or an industry-wide corpus.
- A polished external product interface.
- Large agent orchestration frameworks.
- Optimizing prompts or models before the baseline result is frozen.

## Five gates

### G0 — Source and task contract

Choose the document set, metric families, source locator convention, output
schema, and correctness rules. Resolve ambiguous units and periods before
annotation begins.

### G1 — Human benchmark v0.1

Create 50–100 reviewed items. Include straightforward and difficult examples,
and record exclusions rather than silently discarding ambiguity.

### G2 — Baseline

Run the simplest viable Data Agent path without tuning against the completed
benchmark. Freeze its configuration, trace, outputs, cost, and latency.

### G3 — Evaluation and error analysis

Score the baseline and manually classify every error. Separate at minimum:
source acquisition, parsing, retrieval, extraction, normalization, attribution,
and benchmark ambiguity.

### G4 — Experiment 001

Select one high-impact error class, write a falsifiable hypothesis, change one
factor, rerun the same benchmark, and record result and trade-offs.

## Decisions still to make at G0

These are intentionally not guessed in advance:

1. Which Alphabet document types and date range form benchmark v0.1?
2. Which metric families are representative enough for the first 50–100 items?
3. What counts as correct for reported, derived, restated, and non-GAAP values?
4. How is a source location represented so a reviewer can verify it quickly?
5. Which old Data Agent implementation is the fairest untuned baseline?

## Stop conditions

Pause and reassess if the benchmark cannot be reviewed from primary evidence,
if one item cannot be scored deterministically, or if implementation work grows
beyond the five gates without producing a baseline result.

