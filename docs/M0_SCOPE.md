# M0 Scope — Alphabet Company Business Map

## Status

Approved for implementation planning on 2026-09-06. The Chinese companion is
normative and must remain semantically identical to this document.

## Evaluation question

> Given Alphabet's latest annual 10-K, can the system produce an
> evidence-backed Company Business Map that helps an investor understand what
> the company does, how its major businesses make money, how they relate, and
> what remains unknown?

## Purpose

The Business Map is the starting point for company research. It should help a
researcher find the economically important parts of Alphabet and decide what
to investigate next. It is not an organization chart, an exhaustive product
catalog, or a knowledge graph built for its own sake.

## Fixed input

- Company: Alphabet Inc.
- Filing: Form 10-K for the fiscal year ended December 31, 2025.
- Filed: February 5, 2026.
- SEC accession: `0001652044-26-000018`.
- Benchmark evidence source: the filed 10-K only.

Other filings, earnings calls, news, investor presentations, and external
knowledge may inform later research but cannot be used to establish M0 gold
answers.

## Required output

### 1. Major businesses

Identify the major businesses needed to understand Alphabet. For each one,
record its disclosed name, a concise description, principal products or
services, customers when disclosed, and supporting evidence.

### 2. Economics

Explain how each major business creates value and makes money to the extent
supported by the filing. Distinguish an explicit statement from a reasonable
derivation, and do not fill gaps with outside knowledge.

### 3. Relationships

Record only relationships that improve understanding, such as a business being
reported under another business, a product belonging to a business, or one
business sharing or supporting an economic capability. Do not force every item
into a strict tree.

### 4. Importance signals

Capture evidence that helps a researcher judge current importance, such as
separate segment reporting, disclosed revenue or operating income, management
emphasis, or explicit strategic language. M0 does not require one universal
importance score or a definitive investment ranking.

### 5. Unknowns

State material questions that the 10-K does not answer. Missing disclosure must
remain unknown rather than becoming an Agent inference presented as fact.

## Inclusion rule

Include an item when omitting it would materially weaken a reasonable
investor's understanding of Alphabet's principal businesses or economics and
the filing provides supporting evidence.

Exclude incidental examples, minor features, customers, technologies without
a separately described business role, and product names that add no meaningful
economic understanding. Ambiguous cases must be recorded for human review.

## Gold benchmark workflow

1. A capable Agent proposes a candidate Business Map.
2. A human verifies every statement against the filing.
3. The human searches independently for omissions and duplicates.
4. Unsupported claims are removed; ambiguous claims are marked explicitly.
5. The reviewed reference map and review decisions are frozen as benchmark
   v0.1.

Model agreement can suggest candidates but cannot establish truth. The filed
evidence and human adjudication determine the gold answer.

## M0 evaluation dimensions

- major-business coverage;
- factual correctness;
- business-description correctness;
- economics or monetization correctness;
- relationship correctness;
- evidence support and locator correctness;
- duplicate and unsupported-claim rates;
- unknowns handled without unsupported inference;
- human usefulness review;
- cost and latency as diagnostics.

Objective dimensions and human judgment must be reported separately. M0 does
not collapse them into one score.

## Explicitly out of scope

- Alphabet's actual internal organization chart or reporting lines;
- exhaustive extraction of every named product and feature;
- cross-year change detection;
- a universal business-importance score;
- business momentum, forecasts, or future potential;
- complete financial metric extraction;
- investment thesis, risks, and variant perception;
- other companies and other document families;
- a general-purpose annotation platform or polished external UI.

These are later questions, not rejected capabilities.

## Five gates

### G0 — Business Map contract

Freeze the source representation, evidence locator, inclusion and exclusion
rules, minimum output schema, ambiguity policy, and review rubric. Test the
contract manually on a small 10-K section before implementation.

### G1 — Gold Business Map v0.1

Create and review the reference map from the fixed filing. Preserve evidence,
edits, exclusions, ambiguity, and explicit unknowns.

### G2 — Untuned baseline

Run the simplest viable old or reconstructed Data Agent path without tuning on
the completed gold map. Freeze model, prompts, configuration, code revision,
raw output, traces, cost, and latency.

### G3 — Evaluation and error analysis

Compare the baseline with the gold map and inspect every omission, unsupported
claim, duplicate, incorrect relationship, weak evidence link, and unjustified
inference. Separate source, parsing, extraction, synthesis, evidence, schema,
and benchmark errors.

### G4 — Experiment 001

Select one high-impact error class, state a falsifiable hypothesis, change one
factor, rerun the same benchmark, and record quality and cost trade-offs.

## Stop conditions

Return to G0 if the map becomes an exhaustive product catalog, if a field does
not help company research, if reviewers cannot apply a rule consistently, if a
claim cannot be checked from evidence, or if implementation expands before the
gold map and untuned baseline are frozen.

## Expansion after M0

Proceed one question at a time:

1. use multiple annual filings to evaluate business change;
2. add explicit importance and momentum analysis;
3. connect the Business Map to drivers, risks, and a thesis;
4. validate a stable question on a small company set;
5. introduce each new question on Alphabet before expanding it to more
   companies;
6. expand toward 10, 50, and 100 companies only when evidence justifies it.

