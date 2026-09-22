# Alphabet FY2025 10-K Research Data v0.1-candidate

## Purpose

Publish the current Business Map, field-level claims, disclosed FY2025 metrics,
exact evidence links, document context, and known unknowns behind one immutable
`EvidenceBundle`. This is the first concrete handoff from the Data Agent side
to a future Analysis Agent.

## Contents

- 12 Business Map nodes and 11 relationships;
- 51 field-level claims;
- 13 normalized FY2025 metric points in USD millions;
- 74 exact claim-to-evidence links;
- 22 source-located document contexts;
- 2 explicit unknowns;
- source and Document Index provenance for every evidence link.

## Known limitations

- This release is a candidate, not a frozen benchmark or Gold Answer.
- The accepted review decision to split Subscriptions, Platforms, and Devices
  has not yet been applied; it targets Business Map `v0.3-candidate`.
- Only FY2025 metric points are normalized, so `changes` is intentionally empty.
- The bundle contains no Thesis, Drivers, Risks, or To-Watch judgments.

## Next validation

- Verify that every published claim resolves to the frozen 10-K source.
- Review Business Map `v0.3-candidate` before publishing a successor bundle.
- Use this bundle to test the local `ResearchDataPort`; do not tune an Analysis
  Agent against it until the input candidate is reviewed and frozen.
