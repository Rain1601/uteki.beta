# Algorithm Components — Simplicity First

## Principle

Uteki owns a small, tool-neutral contract for datasets, annotations, agent
runs, predictions, evidence, scores, reviews, and experiments. External tools
may implement storage or interfaces, but no external product owns the meaning
of these objects.

Adopt a component only when it removes an observed bottleneck and remains
replaceable. Do not introduce infrastructure in anticipation of hypothetical
scale.

## M0 default

- version-controlled, human-readable benchmark records;
- explicit schemas and deterministic validators;
- one simple experiment runner;
- transparent metric functions;
- manual review using the smallest usable interface;
- adapters around model providers and optional platforms.

## Candidates, not commitments

- **Argilla** when collaborative annotation and task distribution become a
  real bottleneck.
- **Phoenix** or **Langfuse** when comparing traces and experiment runs becomes
  painful with local artifacts.
- **MLflow** when broader experiment and dataset lifecycle requirements justify
  its tracking server and database.

M0 does not select any of them. The implementation plan must compare an
external component with the smallest in-repository solution using a real
workflow, not a feature checklist.

## Rejection tests

Reject or postpone a component if it:

- requires its own concepts before our annotation contract is stable;
- hides raw inputs, outputs, evidence, or scores;
- makes benchmark versions difficult to export and reproduce;
- couples Agent logic to one vendor or UI;
- adds deployment work before it saves review or experiment time;
- cannot explain a result without consulting the platform itself.

