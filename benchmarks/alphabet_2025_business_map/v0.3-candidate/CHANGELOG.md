# v0.3-candidate

## Problem addressed

The v0.2 candidate incorrectly represented `Subscriptions, Platforms, and Devices` as one operating-business node merely because the 10-K reports their revenue together.

## Changes

- Preserved v0.2 unchanged.
- Replaced the combined business node with three L2 commercial nodes: Google subscriptions, Google platforms, and Google devices.
- Preserved `Google subscriptions, platforms, and devices` as one L3 financial Revenue Line with 2025 revenue of $48.030B.
- Added non-hierarchical `supports` links from the three business nodes to the combined financial line.
- Marked modeling statements as `derived` and direct filing statements as `explicit`.
- Reassigned products and allowed mentions to the corresponding business nodes.
- Recorded the previously accepted review decision as applied in this candidate.

## Validation target

- 15 required nodes;
- 14 hierarchy edges and 3 cross-view `supports` links;
- 57 field-level Claims;
- 80 exact Claim-to-Evidence spans;
- no allocation of the combined $48.030B to Subscriptions, Platforms, or Devices.

## Status

This remains a candidate until every new node, Claim, edge, and exact evidence span is manually reviewed. It must not be used as frozen Gold before approval.
