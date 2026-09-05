# Project Constitution

## Purpose

Build the ability to conduct investment research, construct durable research
data, evaluate automation scientifically, automate only validated work, and
transfer the resulting method to a new company.

## Decision rule

Every substantial addition must name the end-state outcome it improves and
the evidence that would demonstrate improvement. If neither is clear, it does
not enter the active roadmap.

## Working principles

- Move in small, fast, evidence-producing steps. Every step must be independently
  reviewable and small enough to reverse without protecting sunk cost.
- Keep only one active capability milestone. Finish its complete research and
  evaluation loop before expanding horizontally.
- Begin with an investment question, not a feature.
- Run the research loop manually before automating it.
- Preserve source, location, time, and attribution for every material fact.
- Establish a fixed benchmark and baseline before optimization.
- Write a hypothesis before changing the system.
- Evaluate on the same benchmark and inspect every material error.
- Treat methodology as the residue of repeated evidence, not upfront doctrine.
- Keep final investment judgment with the human researcher.

## Scope discipline

The initial scope is intentionally narrow:

- one company: Alphabet;
- one document family: three consecutive Alphabet annual 10-K filings;
- one automation capability: disclosed business-structure extraction;
- one evaluation loop: annotate, baseline, score, review errors, experiment;
- one researcher and final reviewer: the human project owner.

Company discovery, multi-company comparison, portfolio management, a general
research agent, and production UI are end-state capabilities, not current work.
They enter the active roadmap only after the current loop meets its acceptance
criteria.

"Small and fast" does not mean skipping rigor. It means reducing the size of
each claim so that it can be tested quickly and honestly.

## Initial evaluation question

Can the system recover Alphabet's publicly disclosed business entities,
types, relationships, evidence, and cross-year disclosure changes from three
consecutive annual 10-K filings under a fixed annotation policy?

The exact contract is defined in `M0_SCOPE.md` and its Chinese companion.

## M0 acceptance criteria

- A versioned benchmark has explicit annotation instructions.
- A baseline produces predictions using the same item identifiers.
- Evaluation is deterministic and reproducible from one command.
- Missing, incorrect, and malformed outputs are distinguishable.
- Each experiment records a hypothesis, change, benchmark version, result,
  costs, error analysis, conclusion, and next action.
