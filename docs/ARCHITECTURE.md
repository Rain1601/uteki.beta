# Architecture — Modular Monolith

## Status

Approved for implementation planning on 2026-09-06. The Chinese companion is
normative and must remain semantically identical to this document.

## Decision

Uteki Beta begins as one repository and one local deployable application with
strict module boundaries. Agent execution and evaluation are logically
separate but are not separate repositories or services in M0.

The evaluation side may invoke the Agent through its public interface. The
Agent must never depend on benchmarks, gold answers, scorers, reviews, or
experiments.

## Repository structure

```text
uteki.beta/
├── apps/
│   ├── review_workbench/       # Minimal local human-review UI
│   └── cli/                    # Local commands for runs and evaluations
├── src/uteki/
│   ├── domain/                 # Stable business concepts and contracts
│   │   ├── business_map/
│   │   ├── documents/
│   │   ├── evidence/
│   │   └── runs/
│   ├── agents/                 # Agent Execution Plane
│   │   └── business_map/
│   │       ├── contract/
│   │       ├── pipeline/
│   │       ├── prompts/
│   │       └── tools/
│   ├── evaluation/             # Evaluation & Experiment Plane
│   │   ├── datasets/
│   │   ├── scorers/
│   │   ├── experiments/
│   │   └── error_analysis/
│   └── infrastructure/         # Replaceable external adapters
│       ├── document_sources/
│       ├── model_providers/
│       └── storage/
├── data/
│   ├── source_documents/       # Original or normalized research sources
│   ├── agent_runs/             # Inputs, outputs, traces, cost, latency
│   └── evaluation/             # Gold, reviews, scores, experiments
├── benchmarks/                 # Frozen, version-controlled releases
├── experiments/                # Human-readable experiment records
├── tests/
│   ├── unit/
│   ├── contract/
│   └── integration/
└── docs/
```

Directories are created only when the first real file needs them. Empty
architecture scaffolding is not progress.

## Module responsibilities

### Domain

Owns the meaning of Business Map, Business, Relationship, Evidence, Document,
Agent Run, Review Decision, and related identifiers. It contains no model,
database, web, benchmark, or experiment dependencies.

### Agent Execution Plane

Accepts a versioned request and configuration, reads permitted source material,
and produces a Business Map candidate plus a reproducible run record. It does
not know whether the run is a benchmark, experiment, or production task.

### Evaluation & Experiment Plane

Owns datasets, gold answers, scorers, experiment comparisons, error taxonomy,
and evaluation reports. It invokes the Agent through its public contract and
never reaches into Agent internals.

### Review Workbench

Belongs to the Evaluation side. It displays source evidence and an Agent
candidate, then records accept, edit, reject, ambiguous, and omitted-item
decisions. It is a workflow-specific UI, not a general annotation platform.

### Infrastructure

Implements replaceable adapters for SEC documents, model providers, and
storage. Provider SDK objects must not cross into Domain or Agent contracts.

## Allowed dependencies

```text
apps/review_workbench -> evaluation -> agents -> domain
                                \----> domain
apps/cli ------------> evaluation / agents
infrastructure ------> implements ports owned by domain or calling modules
```

Rules:

1. `domain` imports no other Uteki module.
2. `agents` may import `domain`, but never `evaluation` or `apps`.
3. `evaluation` may import Agent public contracts and `domain`, but not Agent
   pipeline internals.
4. `apps` orchestrate modules but contain no business or scoring rules.
5. `infrastructure` is reached through explicit ports or adapters.
6. Shared utilities are added only when two real consumers exist; there is no
   speculative `common` dumping ground.

## Agent public contract

Conceptually, M0 exposes one operation:

```text
BusinessMapRequest + AgentConfig
                ↓
        BusinessMapAgent.run
                ↓
BusinessMapCandidate + AgentRunRecord
```

The request identifies the document and task contract. Configuration records
the model, prompt version, tools, and runtime parameters. The result contains
structured claims and evidence. The run record contains reproducibility,
trace, cost, latency, warnings, and failures.

Gold answers and benchmark identities are never part of the Agent request.

## Data separation

M0 may use one local storage technology, but data namespaces remain separate:

- `source_documents`: filing content and stable source locators;
- `agent_runs`: immutable execution inputs, configurations, raw outputs, and
  traces;
- `evaluation`: candidate-to-gold comparisons, human reviews, scores, and
  experiments;
- `benchmarks`: frozen exported releases suitable for Git review.

The Agent can read approved source documents and write run artifacts. It cannot
read gold answers or evaluation decisions during execution.

## Configuration and secrets

Version-controlled configuration contains provider names, model identifiers,
prompt versions, and non-secret parameters. API keys and credentials are read
at runtime from environment variables or a local ignored secret file. Secrets
from archived repositories may be referenced during local setup but are never
copied into source, documentation, run artifacts, or Git history.

## Extraction rule

Remain a modular monolith until an observed boundary justifies separation.
Consider separate packages or services only when multiple Agent teams share
evaluation, execution needs independent scaling, benchmark access requires
security isolation, ownership diverges, or release cadences become independent.

