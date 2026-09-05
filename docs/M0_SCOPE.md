# M0 Scope — Alphabet Disclosed Business Structure

## Status

Draft for human review. This document defines the active milestone but does
not authorize implementation. The Chinese companion is normative and must
remain semantically identical to this document.

## Evaluation question

> Given Alphabet's annual 10-K filings for three consecutive fiscal years, can
> the system identify the publicly disclosed business entities, classify their
> types, recover their disclosed relationships, attach supporting evidence,
> and detect disclosure changes completely and without duplication under a
> fixed annotation policy?

## Why this is M0

The task is directly useful for understanding a company and can be checked
against primary evidence. It is narrower and more objectively scorable than a
thesis, risk, or business-importance judgment, while still testing document
understanding, classification, relationship extraction, evidence attribution,
and change detection.

## Meaning boundary

The output is an **Alphabet Disclosed Business Structure**, not Alphabet's
actual internal organization chart. A 10-K reflects investor-facing reporting
and description. Absence from the filing does not prove that a business or
organizational unit does not exist internally.

## Inputs

- Company: Alphabet only.
- Sources: primary-source annual 10-K filings only.
- Time span: three consecutive fiscal years, to be fixed at G0.
- Source format and stable locator convention: to be fixed at G0.

Earnings calls, quarterly filings, news, investor presentations, and external
company knowledge are excluded from the benchmark source set in M0.

## Required outputs

### 1. Business nodes

Each included node records its canonical and disclosed names, an entity type
from a fixed taxonomy, filing year, source evidence and stable locator, and an
extraction confidence used only for diagnosis. The initial taxonomy must
distinguish at least reportable segment, business line, product or platform,
and revenue source. G0 defines each type and handles ambiguity.

### 2. Business relationships

Relationships form a graph, not necessarily a strict tree. The initial
taxonomy must distinguish at least `reported_under`, `part_of`, and
`generates_revenue_through`. Every relationship requires direct evidence or an
explicitly documented derivation rule.

### 3. Disclosure changes

Across filing years, the output distinguishes business change, reporting or
classification change, terminology or naming change, description-only change,
and unknown when filings do not support a stronger conclusion. A textual
difference alone must not be labeled as a real business change.

### 4. Evidence

Every node, relationship, and change claim must be reviewable against the
source text. Evidence records the filing, section or item, stable locator, and
the smallest sufficient supporting passage.

## Annotation and gold benchmark

The gold set is built by:

1. defining inclusion, exclusion, type, relationship, and change rules;
2. allowing a capable model or agent to propose candidate annotations;
3. having a human verify every candidate against the filing;
4. having the human search independently for omissions;
5. resolving ambiguous cases explicitly rather than hiding them;
6. freezing the reviewed dataset as benchmark v0.1.

Agent suggestions accelerate annotation but never become ground truth merely
through model agreement. Primary evidence plus human adjudication determines
the released gold set.

## Initial metrics

- node precision and recall;
- entity-type accuracy;
- relationship precision and recall;
- duplicate rate;
- evidence support accuracy;
- change-type precision and recall;
- invalid-output and abstention rates;
- cost and latency as diagnostic metrics.

Metrics must also be reported by filing year, entity type, and error category.
One aggregate score is insufficient.

## Explicitly out of scope

- actual internal organization structure;
- business importance ranking;
- business momentum or future potential;
- financial metric extraction;
- investment thesis, risks, and variant perception;
- company discovery, cross-company comparison, and portfolio management;
- sources other than the frozen 10-K set;
- a polished annotation or external product interface;
- optimization before benchmark v0.1 and the baseline are frozen.

These are later milestones, not rejected capabilities.

## Five gates

### G0 — Annotation contract

Freeze filing years, document representation, locator convention, inclusion
and exclusion rules, node, relationship, and change taxonomies, ambiguity
policy, and scoring rules. Manually annotate a very small pilot and revise the
contract before producing the full gold set.

### G1 — Gold benchmark v0.1

Create and review the complete gold structure for the frozen filings. Keep
source evidence, annotator decisions, exclusions, and unresolved ambiguity.
Measure size in nodes, relationships, changes, and evidence records, not an
arbitrary target number of questions.

### G2 — Untuned baseline

Run the simplest viable old or reconstructed Data Agent path without tuning on
the completed benchmark. Freeze model, prompts, configuration, code revision,
raw output, traces, cost, and latency.

### G3 — Evaluation and error analysis

Score the baseline and inspect every false positive, false negative, duplicate,
unsupported relation, and incorrect change classification. Separate source,
parsing, ontology, extraction, normalization, evidence, temporal alignment,
and benchmark errors.

### G4 — Experiment 001

Select one high-impact error class, state a falsifiable hypothesis, change one
factor, rerun the same benchmark, and record quality and cost trade-offs.

## Stop conditions

Pause and return to G0 if two careful reviewers cannot apply a rule
consistently, if an item cannot be checked from its evidence, if a change claim
cannot distinguish text from business reality, or if implementation grows
before the benchmark and untuned baseline are frozen.

## Expansion rule after M0

Expand one axis at a time:

1. keep the task fixed and test it on a small company set;
2. stabilize cross-company behavior before increasing company count;
3. introduce one new research task on Alphabet first;
4. expand that validated task to the existing company set;
5. grow toward 10, then 50, then 100 companies only when observed errors and
   operational value justify the next scale.

Company counts are direction markers, not delivery targets. Each expansion
requires an explicit gate based on benchmark quality and generalization.

