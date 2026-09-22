# Alphabet FY2025 Business Map Annotation Policy · v0.3 Candidate

## Status

This is a candidate reference answer, not a frozen benchmark. It applies the approved SPD dual-structure decision but still requires human review of every node and Claim.

## Target question

Can the system recover the business composition, hierarchy, business content, and financial disclosure scale in Alphabet's FY2025 10-K without forcing business ontology and financial presentation into one structure?

## Two structures

- The **business structure** answers which distinct commercial activities the company provides: Subscriptions, Platforms, and Devices are separate L2 nodes.
- The **financial disclosure structure** answers how the 10-K aggregates revenue: `Google subscriptions, platforms, and devices` is one L3 Revenue Line.
- Each business node has a `supports` edge to the combined Revenue Line, but `supports` is not a parent edge.
- The $48.030B must not be allocated among the three business nodes because the 10-K does not provide that split.

## Minimum-node rule

A core node is the finest economically meaningful filing-supported unit. It must be explicitly named, or explicitly enumerated and human-adjudicated as a distinct commercial activity, and satisfy at least one condition:

1. it is a reportable segment;
2. it has a separate financial disclosure;
3. the filing gives it an independent business or monetization description;
4. it is a stable business group required to understand its parent.

Products, brands, features, and disclosed examples remain `allowed mentions` by default. Do not infer Alphabet's internal organization.

## Levels

- `L0`: company context;
- `L1`: reporting structure;
- `L2`: commercial business or offering group;
- `L3`: separately disclosed financial revenue line;
- `L4`: product, brand, feature, or disclosed example; not a core scored node.

This version has 15 required nodes. `business_architecture` scores L0–L2. `financial_disclosure` additionally scores L3, but the combined view must not be interpreted as a pure organization tree.

## Adjudication labels

- `required`: expected in extraction and included in precision and recall;
- `allowed`: permitted supporting detail, neutral for node recall;
- `unsupported`: a node or relationship unsupported by the fixed 10-K.

Every required node, hierarchy edge, cross-view link, and financial value must resolve to the fixed Source Snapshot. `derived` may express an explicit modeling decision but must not be presented as a direct filing statement.
