# G0 Contract — Company Business Map v0.1

## Status

Pilot contract derived from Alphabet's 2025 10-K Item 1. It must be tested by
the baseline and Review Workbench before it can become benchmark v0.1.

## Smallest useful objects

### BusinessMap

- `schema_version`
- `company_id`
- `document_id`
- `summary`
- `businesses[]`
- `relationships[]`
- `unknowns[]`
- `evidence[]`

### Business

- `id`: stable within the map;
- `name`: filing-disclosed name;
- `kind`: `company`, `reportable_segment`, `business`, or `offering_group`;
- `description`: concise economic description;
- `products_services[]`: representative, not exhaustive;
- `customers[]`: only when disclosed;
- `monetization[]`: explicit or clearly marked derived statements;
- `importance_signals[]`: evidence, not a universal score;
- `evidence_ids[]`;
- `review_status`: `candidate`, `accepted`, `edited`, `rejected`, or
  `ambiguous`.

### Relationship

- `source_id`, `target_id`;
- `kind`: `reported_under`, `part_of`, or `supports`;
- `description`;
- `evidence_ids[]`;
- `review_status`.

Direction is child/source to parent/target for `reported_under` and `part_of`.
`supports` is directional and must not imply ownership.

### Evidence

- `id`;
- `document_id`;
- `section_path[]`;
- `paragraph_ordinal` within the normalized document;
- `text_hash` of normalized paragraph text;
- `source_url`;
- `support`: a concise explanation of what the passage supports.

Raw source text remains in the source document and is not duplicated into the
benchmark. Section path is a human-readable hint; document paragraph ordinal
and text hash form the machine locator and detect source or parser drift.

### Unknown

- `id`;
- `question`;
- `materiality`;
- `related_business_ids[]`;
- `reason_unanswered`;
- `evidence_ids[]` when the disclosure gap itself has an anchor.

## Inclusion test

Include a candidate only if all answers are yes:

1. Does the filing name or unambiguously describe it?
2. Does it materially improve understanding of what Alphabet does or how it
   makes money?
3. Can a reviewer verify it from a specific passage?
4. Is it not already represented by another node?

Named products normally belong in `products_services`, not as separate
business nodes. Promote one only when the filing gives it a distinct economic
role needed for the map.

## Assertion discipline

- `explicit`: directly stated by the filing;
- `derived`: follows from an approved deterministic rule;
- `unknown`: not supported by the fixed source.

M0 permits derived statements only when the derivation rule and all evidence
are stored. Agent confidence never upgrades a derived or unknown statement.

## Pilot result

The Item 1 pilot demonstrates that a small map can represent Alphabet, Google,
Google Services, Google Cloud, Other Bets, and selected economically distinct
offerings without creating a node for every named product. It also demonstrates
that shared AI infrastructure is better represented by a `supports` relation
than forced into a single ownership tree.
