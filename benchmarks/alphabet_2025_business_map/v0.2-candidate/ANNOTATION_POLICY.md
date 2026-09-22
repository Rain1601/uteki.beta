# Alphabet FY2025 Business Map Annotation Policy · v0.2 Candidate

## Status

This is a candidate reference answer, not a frozen benchmark. It is used to adjudicate node granularity and evidence and must not be treated as scoring gold before approval.

## Target question

Can the system recover the filing-disclosed business composition, hierarchy, business content, and disclosed scale from Alphabet's FY2025 10-K?

## Minimum-node rule

A core node is the finest economically meaningful filing-disclosed unit that can be supported by source evidence. It must be explicitly named, its parent relationship must be evidenced, and it must satisfy at least one condition:

1. it is a reportable segment;
2. it has a separate financial disclosure;
3. the filing gives it an independent business or monetization description;
4. it is a stable business group required to understand its parent.

Products, brands, features, and disclosed examples are `allowed mentions` by default and do not count toward core-node recall. Promote one only when the filing gives it an independent disclosed economic role. Do not infer the company's internal organization.

## Levels

- `L0`: company context;
- `L1`: reporting structure;
- `L2`: commercial business or offering group;
- `L3`: separately disclosed financial revenue line;
- `L4`: product, brand, feature, or disclosed example; not a core scored node.

The default `financial_disclosure` profile scores the 12 required L0–L3 nodes. Results may also be reported separately for:

- `reporting_structure`: L0–L1;
- `business_architecture`: L0–L2;
- `financial_disclosure`: L0–L3.

## Adjudication labels

- `required`: expected in extraction and included in precision and recall;
- `allowed`: permitted supporting detail, neutral for node recall;
- `unsupported`: a node or relationship that the fixed 10-K cannot support.

Scale and importance are node attributes, not inclusion criteria. Every required node, parent edge, and financial value must resolve to evidence in the fixed Source Snapshot.

