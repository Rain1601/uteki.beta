# M1 Scope — Alphabet 10-K-Bounded Operating Thesis

## Status

Approved by the user on 2026-09-13 and amended the same day after the Data
Agent / Analysis Agent responsibility boundary was clarified. The Chinese
companion is normative and the English version must remain semantically
identical. M1 is not yet the active implementation milestone and must not
interrupt M0's Business Map benchmark, baseline, scoring, or Experiment 001.

## Evaluation question

> Given versioned EvidenceBundles produced by the Data Agent from Alphabet's
> FY2025 10-K and a human-reviewed Business Map, can the Analysis Agent use
> controlled ResearchDataPort queries to produce an evidence-backed, causal,
> falsifiable, and monitorable 10-K-bounded Operating Thesis Candidate?

The fixed research question is:

> Based only on Alphabet's FY2025 10-K, what operating thesis best explains
> how Alphabet currently creates value, and which three key drivers are most
> likely to strengthen or weaken that operating trajectory over the next three
> years?

## Artifact definition

The M1 artifact is a `10-K Bounded Operating Thesis Candidate`, not a final
Investment Thesis.

It may express:

- a Primary Bet grounded in the 10-K;
- no more than three key operating Drivers;
- no more than two key Risks that could break the Primary Bet;
- actionable To-Watch items linked to every Driver and Risk;
- supporting evidence, contradicting evidence, interpretations, hypotheses,
  and unknowns;
- an explicit three-year research horizon and versioned as-of point.

It must not express:

- current market expectations or Variant Perception;
- current valuation, price target, or expected return;
- buy, sell, position-size, or trading recommendations;
- operating changes after the 10-K filing date;
- unsupported claims about the latest situation;
- statements promoted to fact only because the model is confident.

Without market expectations and price, the result is an Operating Thesis, not
a complete Investment Thesis.

## Fixed input

- Company: Alphabet Inc.;
- filing: Form 10-K for the fiscal year ended December 31, 2025;
- filed: February 5, 2026;
- SEC accession: `0001652044-26-000018`;
- data source boundary: frozen Alphabet FY2025 10-K Source Snapshot;
- Data Agent input index: `alphabet_2025_10k/indexes/v0.1`;
- direct Analysis Agent input: the immutable `data_snapshot_id` and
  `evidence_bundle_ids[]` published by the Data Agent;
- fact foundation: the human-reviewed Business Map released by M0 and exposed
  through ResearchDataPort;
- external materials: prohibited;
- internet retrieval: prohibited;
- model prior knowledge: inadmissible as factual evidence.

Every run records the exact `data_snapshot_id`, `evidence_bundle_ids[]`,
`business_map_version`, and research-question version. The underlying
`source_snapshot_id` and `document_index_id` remain fully traceable through
each EvidenceBundle, but are not direct inputs that let the Analysis Agent
bypass the Data Agent. No official M1 baseline may run before the M0 Business
Map is frozen.

The detailed handoff rules are defined in
[`DATA_ANALYSIS_AGENT_CONTRACT.md`](DATA_ANALYSIS_AGENT_CONTRACT.md).

## Minimum research flow

```text
Frozen 10-K
→ Data Agent Processing
→ Versioned Research Data / EvidenceBundle
→ Research Question
→ Research Data Query Plan
→ Active ResearchDataPort Queries
→ Primary Bet and Driver Candidates
→ Risk and Counter-Evidence Challenge
→ To-Watch Candidates
→ Thesis Synthesis
→ Human Review
→ Versioned Candidate
```

Each step must have its own run record. The first version must not use one
prompt to read the entire 10-K and directly emit a final thesis.

## LLM call boundaries

### R0 — Retrieval plan

Inputs:

- the fixed Research Question;
- the task contract and source boundary;
- the data catalog, available data types, and source boundary published by
  ResearchDataPort;
- the reviewed Business Map summary, object identifiers, and version;
- identifiers and coverage of currently available EvidenceBundles.

Outputs:

- proposed ResearchDataQueries;
- Business Map, Claim, Metric, Evidence, or Document Context objects to read;
- fact types to locate;
- questions that cannot yet be answered.

R0 must not produce the final Thesis.

### R1 — Active research-data queries

The Analysis Agent uses read-only ResearchDataPort queries to inspect research
data published by the Data Agent. The Data Agent may use Document Navigator
internally to parse nodes, blocks, and tables. The Analysis Agent must not
parse SEC HTML directly or bypass ResearchDataPort to read underlying files.

Outputs:

- ResearchDataQuery identifiers and returned EvidenceBundle identifiers;
- identifiers of Business Map, Claim, Metric, Evidence, and Document Context
  objects read;
- evidence candidates with source-resolvable locators;
- failed retrievals and missing results;
- the complete tool-call trace.

R1 is a re-entrant query loop, not one preprocessing pass. If R2–R4 discover
an evidence gap, they may only create a `ResearchDataRequest`. After the Data
Agent fulfills it and publishes a new EvidenceBundle, the flow re-enters R1.
The Analysis Agent must not parse the source or fill the gap itself.

### R2 — Primary Bet and Driver candidates

Inputs:

- Research Question;
- reviewed Business Map;
- evidence obtained in R1;
- Driver output schema.

The output contains one draft Primary Bet and no more than three
non-duplicative Drivers. The Primary Bet directly answers the Research
Question. Each Driver states its operating mechanism, possible financial
impact, time horizon, supporting evidence, contradicting evidence, and
unknowns.

Three is a maximum number of output slots, not a quota. When evidence is
insufficient, a slot remains empty or Unknown rather than being filled with a
weak candidate.

### R3 — Risk and counter-case challenge

Inputs:

- Research Question;
- draft Primary Bet;
- Driver Candidates;
- evidence concerning risk, competition, capital allocation, and uncertainty.

The output contains no more than two key Risks. Each Risk includes a failure
mechanism, affected Drivers, supporting evidence, contradicting evidence, and
candidate Kill Criteria. An Item 1A heading or generic risk cannot directly
become a Thesis Risk.

### R4 — To Watch

Inputs:

- Driver Candidates;
- Risk Candidates;
- metrics, disclosures, and future validation paths identifiable from the
  fixed source.

Every Driver and Risk has at least one WatchItem. If the current scope cannot
define an actionable observation method, it is explicitly marked
`not_observable_from_current_scope`.

### R5 — Thesis synthesis

Inputs are limited to:

- Research Question;
- reviewed Business Map;
- structured candidates from R2–R4;
- supporting and contradicting Evidence;
- Material Unknowns.

The output is one structured Thesis Candidate. R5 must not introduce a new
fact that was not recorded in an earlier step.

## ResearchDataPort query contract

M1 exposes at most these read-only capabilities to the Analysis Agent:

```text
get_business_map(company_id, version)
search_research_data(company_id, query, source_policy_id)
get_claim_evidence(claim_id)
get_metric_series(metric_id, periods)
get_document_context(evidence_ids)
compare_periods(company_id, periods, data_types)
request_missing_data(research_data_request)
```

Rules:

1. ResearchDataPort returns only published data allowed by the specified
   `source_policy_id`.
2. Every fact carries a stable Data Object identifier, version, and Source
   Locator.
3. A search result is not automatically Evidence; the Analysis Agent must
   cite concrete Evidence from an EvidenceBundle.
4. Every call records arguments, returned identifiers, order, latency, and
   failure.
5. If evidence is insufficient, the Analysis Agent creates a
   `ResearchDataRequest` or returns Unknown.
6. The Analysis Agent must not fill source gaps from model memory or parse raw
   SEC files directly.
7. When the Data Agent adds or corrects data, it publishes a new immutable
   EvidenceBundle instead of mutating an existing one.
8. The same data snapshot, query, tool version, and configuration must yield
   reproducible query results.
9. The first version implements ResearchDataPort over local files. It does not
   add a separate service, PageIndex, a vector database, or open-web search.

## Minimum data contract

### ResearchQuestion

- `question_id`;
- `question`;
- `company_id`;
- `horizon`;
- `decision_scope`: fixed to `operating_research`;
- `source_policy_id`;
- `version`.

### ThesisCandidate

- `thesis_id`;
- `version`;
- `source_as_of`: fixed to the 10-K filing date;
- `created_at`;
- `question_id`;
- `primary_bet`;
- `conclusion`;
- `horizon`;
- `driver_ids[]`;
- `risk_ids[]`;
- `watch_item_ids[]`;
- `supporting_evidence_ids[]`;
- `contradicting_evidence_ids[]`;
- `unknown_ids[]`;
- `confidence`;
- `review_status`.

### DriverCandidate

- `driver_id`;
- `statement`;
- `mechanism`;
- `affected_business_ids[]`;
- `financial_impact`;
- `expected_direction`;
- `time_horizon`;
- `supporting_evidence_ids[]`;
- `contradicting_evidence_ids[]`;
- `unknown_ids[]`;
- `assertion_type`;
- `review_status`.

### RiskCandidate

- `risk_id`;
- `statement`;
- `failure_mechanism`;
- `affected_driver_ids[]`;
- `impact`;
- `candidate_kill_criteria[]`;
- `supporting_evidence_ids[]`;
- `contradicting_evidence_ids[]`;
- `assertion_type`;
- `review_status`.

### WatchItemCandidate

- `watch_item_id`;
- `linked_type`: `thesis | driver | risk`;
- `linked_id`;
- `question`;
- `observable`;
- `metric_or_signal`;
- `expected_direction`;
- `support_condition`;
- `warning_condition`;
- `falsification_condition`;
- `future_source_types[]`;
- `cadence`;
- `rationale_evidence_ids[]`;
- `review_status`.

### EvidenceLink

- `evidence_id`;
- `document_id`;
- `node_id`;
- `block_id`;
- `text_hash`;
- `quote`;
- `stance`: `supports | contradicts | context`;
- `supports_field`;
- `source_url`.

### Unknown

- `unknown_id`;
- `question`;
- `materiality`;
- `related_ids[]`;
- `reason_unanswered`;
- `next_source_type`.

### AgentRunRecord

- `run_id`;
- `task_type`;
- `question_id`;
- `data_snapshot_id`;
- `evidence_bundle_ids[]`;
- `research_data_query_ids[]`;
- `source_snapshot_ids[]`: provenance inherited from EvidenceBundles;
- `document_index_ids[]`: provenance inherited from EvidenceBundles;
- `business_map_version`;
- `model_provider`;
- `model_id`;
- `prompt_version`;
- `schema_version`;
- `configuration`;
- `tool_trace[]`;
- `raw_output_ref`;
- `structured_output_ref`;
- `code_revision`;
- `started_at`;
- `finished_at`;
- `cost`;
- `latency`;
- `warnings[]`;
- `failure`.

## Assertion types

Every material statement is classified as:

- `explicit_fact`: stated directly by the 10-K;
- `derived_interpretation`: inferred from explicit evidence through an
  explainable chain of reasoning;
- `research_hypothesis`: a judgment requiring future evidence;
- `unknown`: unsupported by the fixed source.

A Thesis or Driver is normally an Interpretation or Hypothesis. Citing
multiple facts does not automatically turn the synthesis into a fact.

## Human reference and benchmark

M1 does not assume that a Thesis has one uniquely correct wording and does not
use exact string matching to establish a gold answer.

Reference-set workflow:

1. A capable Agent may propose a Reference draft outside the baseline, but a
   human must independently verify it against the fixed source and make every
   final adjudication.
2. Every Driver, Risk, WatchItem, and EvidenceLink is reviewed individually.
3. Excluded candidates and exclusion reasons are preserved.
4. Allowed alternative formulations and ambiguity are recorded explicitly.
5. The Reference, Annotation Policy, and Review Decisions are frozen.
6. The baseline prompt cannot be tuned against the complete reference before
   it is frozen.

## Evaluation dimensions

### Deterministic metrics

- schema validity;
- Evidence Locator resolution rate;
- quote-to-source consistency;
- unsupported factual-claim rate;
- source-boundary violation rate;
- tool-trace completeness;
- count constraints and citation completeness;
- duplicate Driver/Risk rate.

### Human rubric

- whether the Primary Bet answers the Research Question;
- whether Drivers are material, distinct, and causally explicit;
- whether Risks can materially break the Thesis rather than summarize generic
  filing risks;
- whether both supporting and contradicting evidence were sought;
- whether WatchItems are specific, actionable, and falsifiable;
- whether Unknowns honestly preserve source limits;
- whether the conclusion is consistent with the preceding structured work;
- whether the output is useful as the starting point for further research.

Objective metrics and the human rubric are reported separately rather than
collapsed into one score. M1 does not evaluate future returns, stock-picking
accuracy, or realized operating outcomes.

### Layered attribution

Evaluation preserves two independent paths:

1. Data Agent: fixed 10-K to EvidenceBundle, evaluated for factual accuracy,
   coverage, structure, numbers, and Evidence location.
2. Analysis Agent: frozen and approved EvidenceBundle to Thesis Candidate,
   evaluated for question answering, Driver selection, causal reasoning,
   counter-evidence, Risks, and To Watch.
3. An end-to-end result may be reported separately, but a single score must
   never hide the two error layers, and missing Data Agent output must not be
   counted as an Analysis Agent reasoning error.

## Versioning and storage

The first version continues to use immutable JSON artifacts and adds no
database:

```text
data/agent_runs/alphabet_2025_10k_thesis/<run_id>/
├── request.json
├── research_data_query_plan.json
├── research_data_trace.jsonl
├── evidence_bundles.json
├── evidence.json
├── drivers.json
├── risks.json
├── watch_items.json
├── thesis_candidate.json
├── raw_outputs/
└── manifest.json
```

The reviewed reference release lives under:

```text
benchmarks/alphabet_2025_10k_thesis/v0.1/
```

Any correction to reviewed content creates a new version. Dynamic
Observations, ongoing monitoring, and SQLite-backed state belong to the later
In-the-Flow milestone.

## Five gates

### T0 — Scope and contract

Review the Research Question, source boundary, Data/Analysis Agent handoff
contract, ResearchDataPort, call decomposition, evaluation rubric, and stop
conditions.

### T1 — Human reference

Outside the baseline pipeline, create a Reference Candidate from the same
10-K. A capable Agent may assist with proposals, but every item must be
independently verified and adjudicated by a human. Also verify that the
three-Driver, two-Risk, and To-Watch structure is genuinely useful.

### T2 — Untuned active-retrieval baseline

Freeze the model, prompts, ResearchDataPort version, EvidenceBundles,
configuration, and complete trace, then run the simplest baseline once.

### T3 — Evaluation and error analysis

Compare the baseline with the Reference. First separate Data Agent, handoff
contract, Analysis Agent, and Benchmark errors; then classify query, evidence,
causal reasoning, Driver selection, Risk, Watch, synthesis, and schema errors.

### T4 — Experiment 001

Select one high-impact error type, state a hypothesis in advance, change one
factor, and record changes in quality, cost, and latency.

## Acceptance criteria

- Every factual premise comes from an EvidenceBundle and resolves onward to a
  Block in the fixed 10-K.
- Every ResearchDataPort call can be replayed and audited.
- The Analysis Agent never reads or parses SEC HTML directly.
- Data-extraction errors and analysis-reasoning errors can be attributed
  independently.
- The output has no more than three Drivers and two Risks and does not invent
  content to fill slots.
- Every Driver and Risk has supporting evidence, a counter-case check, and a
  WatchItem, or explicitly states that it is not observable.
- The Thesis introduces no new fact absent from prior structured steps.
- External knowledge, current market data, and investment recommendations are
  absent.
- A human reviewer can explain why every item was retained, edited, or
  rejected.
- The same inputs and configuration produce comparable run snapshots.

## Stop conditions

Return to T0 when any of the following occurs:

- the fixed Research Question requires external material;
- reviewers cannot consistently distinguish Drivers from products, trend
  labels, or financial metrics;
- Risks collapse into an Item 1A summary;
- WatchItems have no observable target;
- the Analysis Agent relies on model memory instead of EvidenceBundle data;
- the Analysis Agent bypasses ResearchDataPort to read or parse raw SEC files;
- data errors and analysis errors cannot be separated using versions and
  traces;
- one super-prompt replaces diagnosable staged runs;
- the Thesis is presented as a current investment recommendation;
- M1 implementation obstructs completion of M0.

## Explicitly deferred

- 10-Qs, earnings calls, news, investor materials, and competitor filings;
- consensus expectations, Variant Perception, and valuation;
- Bull/Base/Bear price targets and probability-weighted returns;
- catalyst calendars and real-time alerts;
- Observations, Thesis Updates, and continuing version transitions;
- Portfolio Factors, sizing, and trading plans;
- multi-company expansion;
- multi-Agent teams;
- PageIndex, vector databases, and open-web search.
