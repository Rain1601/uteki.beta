# Algorithm Components — Simplicity First

## Principle

Uteki owns a small, tool-neutral contract for datasets, annotations, agent
runs, predictions, evidence, scores, reviews, and experiments. External tools
may implement storage or interfaces, but no external product owns the meaning
of these objects.

Adopt a component only when it removes an observed bottleneck and remains
replaceable. Do not introduce infrastructure in anticipation of hypothetical
scale.

## M0 decision

**Accepted on 2026-09-06:** build a minimal local Review Workbench instead of
adopting Argilla, Label Studio, Doccano, or an experiment platform for M0.

The workbench is a thin interface over Uteki-owned schemas. It is not a new
general-purpose annotation platform. Its first version supports only the
approved Business Structure workflow:

- display a source passage and stable locator;
- review an Agent-proposed node, relationship, or disclosure change;
- accept, edit, reject, or mark the proposal ambiguous;
- add an omitted annotation manually;
- preserve the candidate, human revision, status, and review note;
- export a frozen, version-controlled gold benchmark.

The implementation technology remains open until planning. The plan should
choose the smallest local UI that handles this workflow clearly.

## M0 defaults

- version-controlled, human-readable benchmark records;
- explicit schemas and deterministic validators;
- one simple experiment runner;
- transparent metric functions;
- manual review using the smallest usable interface;
- adapters around model providers and optional platforms.

## Deferred candidates

- **Argilla** when collaborative annotation and task distribution become a
  real bottleneck.
- **Phoenix** or **Langfuse** when comparing traces and experiment runs becomes
  painful with local artifacts.
- **MLflow** when broader experiment and dataset lifecycle requirements justify
  its tracking server and database.

M0 does not select any of them. Reconsider an external component only after an
observed bottleneck such as multiple regular annotators, task distribution,
hundreds of review items, reviewer agreement, or excessive maintenance cost.

## Rejection tests

Reject or postpone a component if it:

- requires its own concepts before our annotation contract is stable;
- hides raw inputs, outputs, evidence, or scores;
- makes benchmark versions difficult to export and reproduce;
- couples Agent logic to one vendor or UI;
- adds deployment work before it saves review or experiment time;
- cannot explain a result without consulting the platform itself.
