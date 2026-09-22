# v0.2-candidate

## Problem addressed

The v0.1 candidate stored Google Search & other, YouTube ads, and Google Network as three generic fields on Google Advertising. That made independently disclosed revenue lines impossible to score as nodes and made their parent relationships implicit.

## Changes

- Preserved the v0.1 candidate unchanged.
- Added three `revenue_line` nodes under Google Advertising.
- Added the explicit `revenue_component_of` relationship kind.
- Added independently reviewable identity, description, monetization, and 2025 revenue claims for each revenue line.
- Added a machine-readable benchmark policy with L0–L3 scoring profiles and L4 allowed mentions.
- Kept named products and disclosed examples out of required node recall.

## Evidence

No new source assertions were introduced. The promoted nodes reuse the existing fixed evidence for the Google Advertising composition, the three component descriptions, the advertising model, and the FY2025 revenue table.

## Validation target

- 12 required nodes;
- 11 parent relationships;
- 51 field-level claims;
- 74 exact claim-to-evidence spans;
- all evidence remains resolvable to the frozen Alphabet FY2025 10-K source snapshot.

## Known decisions still requiring review

- Whether `other enterprise services` should remain an allowed mention rather than a required Google Cloud child.
- The candidate must remain unfrozen until the node tree and every promoted claim are manually reviewed.

## Review decision recorded after generation

The combined `Google subscriptions, platforms, and devices` node was rejected as a business-ontology node. The next candidate will split Subscriptions, Platforms, and Devices into three business nodes and preserve the combined $48.030B amount as a separate financial disclosure bucket. See `review_decisions.json`.
