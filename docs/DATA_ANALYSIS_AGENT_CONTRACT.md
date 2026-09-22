# Data Agent / Analysis Agent Handoff Contract v0.1

## Status

Established on 2026-09-13 from the user-confirmed responsibility boundary.
The Chinese companion is normative and the English version must remain
semantically identical. This contract constrains the design without requiring
separate repositories, processes, or services.

## Core boundary

```text
Raw Research Materials
    ↓
Data Agent
    ↓
Versioned Research Data
    ↓ ResearchDataPort
Analysis Agent
    ↓
Thesis / Drivers / Risks / To Watch
```

The Data Agent owns what the materials say. The Analysis Agent owns what those
facts mean for a research question. The two must not be mixed in one output.

## Data Agent ownership

The Data Agent owns:

- source acquisition, hashes, provenance, and time;
- structure and indexes for documents such as 10-Ks and 10-Qs;
- Blocks, Tables, Assets, and original-source locators;
- Business Maps, factual Claims, financial Metrics, and period changes;
- Evidence Links, parsing diagnostics, missing data, and data quality;
- model, prompt, tool, configuration, and trace for every data-processing run.

The Data Agent does not own theses, Driver prioritization, Risk judgments,
valuation, or trading recommendations.

## Analysis Agent ownership

The Analysis Agent owns:

- Research Questions;
- Primary Bets;
- Key Drivers and causal mechanisms;
- Thesis Risks, counter-cases, and Kill Criteria;
- To-Watch validation protocols;
- Operating Thesis Candidates and their versions;
- the effect of a new EvidenceBundle on existing judgments.

The Analysis Agent must not parse raw SEC HTML, rewrite Data Agent facts, hide
source gaps, or treat model prior knowledge as Evidence.

## ResearchDataQuery

Every Analysis Agent query contains:

- `query_id`;
- `company_id`;
- `question`;
- `requested_data_types[]`;
- `periods[]`;
- `source_policy_id`;
- `related_research_ids[]`;
- `minimum_evidence_level`;
- `created_at`.

A query describes a research need and does not prescribe the Data Agent's
internal pipeline, prompt, or model.

## EvidenceBundle

The Data Agent returns an immutable Bundle containing:

- `bundle_id`;
- `query_id`;
- `source_policy_id`;
- `data_snapshot_id`;
- `source_snapshot_ids[]`;
- `document_index_ids[]`;
- `business_map_version`;
- `claims[]`;
- `metrics[]`;
- `changes[]`;
- `evidence_links[]`;
- `document_context[]`;
- `unknowns[]`;
- `quality_diagnostics[]`;
- `generated_at`.

Every Claim, Metric, and Change resolves through an Evidence Link to a Source
Snapshot. A Bundle may contain source excerpts for analysis and human review,
but the Data Agent continues to own raw document structure.

## Missing-data request

If an EvidenceBundle is insufficient, the Analysis Agent returns a
`ResearchDataRequest` containing:

- `request_id`;
- `research_question`;
- `missing_information`;
- `why_material`;
- `suggested_source_types[]`;
- `company_id`;
- `periods[]`;
- `related_driver_or_risk_ids[]`;
- `priority`;
- `status`.

The Data Agent may fulfill, partially fulfill, reject, or mark the request
unanswerable from the current sources. It emits a new Bundle or an explicit
Unknown and never silently overwrites an old Bundle.

## Interfaces available to the Analysis Agent

The first version exposes only:

```text
get_business_map(company_id, version)
search_research_data(company_id, query, source_policy_id)
get_claim_evidence(claim_id)
get_metric_series(metric_id, periods)
get_document_context(evidence_ids)
compare_periods(company_id, periods, data_types)
request_missing_data(research_data_request)
```

`ResearchDataPort` defines these interfaces. Local files, SQLite, or a future
service may implement them; the Analysis Agent does not depend on storage.

## Version rules

1. An Analysis Run pins one or more `bundle_id` values.
2. An EvidenceBundle is immutable after creation.
3. A Data Agent correction creates a new `data_snapshot_id` and Bundle.
4. A changed data layer never mutates a published Thesis automatically.
5. New data creates an Analysis Update Candidate; human review creates the
   next Thesis Snapshot.
6. Every result preserves both `source_as_of` and actual `created_at`.

## Error ownership

- source download, parsing, table, numeric, entity, period-alignment, or
  Evidence-location errors belong to the Data Agent;
- an unclear query or a request for nonexistent data belongs to the handoff
  contract;
- wrong Driver selection, causal reasoning, counter-evidence handling, or
  synthesis on correct data belongs to the Analysis Agent;
- inconsistent human References or scoring rules belong to Evaluation;
- information unavailable from allowed sources is Unknown, not a factual
  error by either Agent.

## Hard rules

- Data and Analysis Agents keep separate run records and evaluations.
- Every fact used by the Analysis Agent comes from an EvidenceBundle.
- The Analysis Agent may actively query Research Data but cannot bypass the
  Port to access raw materials.
- The Data Agent may use an LLM to process materials, but its inferences are
  labeled and subjected to data evaluation.
- Gold answers, review decisions, and evaluation scores never enter a tested
  Agent's inputs.
- The first version remains a modular monolith and does not split services
  merely because the logical roles are separate.

## Product surface ownership

`/result` is a read-only inspector for the `EvidenceBundle` published by the
Data Agent. Business Map is one view of that structured data; the page is
neither a Gold Benchmark nor an Analysis Agent Thesis, Factors, Risks, or To
Watch result.
