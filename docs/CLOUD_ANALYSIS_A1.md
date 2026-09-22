# A1 · Controlled missing data and source recovery

## Status and purpose

The user approved A0 `analysis-a6a15b4ee5167df6`. Its append-only decision pins hashes of the answer, input, calculations, trace, evaluation and run metadata; historical artifacts are unchanged.

A1 is a new experiment pending review: when one known annual value is missing, can the Analysis Agent request Data-side recovery and finish the original question using cited data? No additional company, Thesis or general search.

## Method

Derive a temporary input by withholding Google Cloud FY2025 revenue and evidence unused by other facts. The approved parent remains unchanged. The derived snapshot has its own ID/hash and does not inherit approval. The model receives neither the withheld value nor the evaluation reference.

New `source_lookup(predicate, period)`:

1. Requires an exact `facts` query for that metric/period returning `not_extracted` first.
2. Data side re-reads fixed SEC HTML and the frozen Document Index using the existing source-only Cloud rule extractor over Part I Item 1 / Part II Item 8.
3. Returns the requested fact, source location, table cell, year and unit verification. Source SHA must match; the approved snapshot is not used to supply the answer.
4. Newly extracted facts get a new ID and pending-review status in a separate experimental overlay. Analysis must retrieve evidence before citing them in the final answer.
5. Unsupported periods return `unsupported_scope`, not a claim of absence from the filing. No new material is downloaded.

This is a deterministic fixed-company/metric adapter, **not general document retrieval or proof of new LLM extraction ability**. One controlled gap does not establish real-world missing-data recall.

## Observed run

`analysis-9373e1c4632a063d`: 9 rounds and 20 tool calls.

- The model first paginated metric data and noticed FY2025 revenue was unavailable.
- Step 6 attempted source_lookup before querying that exact year; the guard rejected it.
- Step 7 queried revenue/FY2025 and received not_extracted; step 8 recovered it successfully.
- Data side extracted 58,705 USD millions from the segment table on reported page 87. The approved parent cited the separate revenue table on page 60; both are valid evidence in the same filing.
- The model cited the recovered fact/evidence, completed six comparisons, and explicitly noted pending review in its limitations.

The model corrected its action from tool feedback. The rejection and original model answer were not removed or rewritten.

## Checks and limits

A separate process replays actions, verifies an observed gap precedes successful recovery, verifies the parent hash is unchanged, and compares recovered/withheld values on the evaluation side. Six annual facts and six comparisons passed checks. Zero evaluation errors does not mean zero tool errors: one rejected call is separately shown in the inspector.

Tests cover gap isolation, prerequisite checks, source re-extraction, source-hash mismatch, unsupported periods, artifact-pinned human approval and live-run replay. 77 unit/regression tests passed.

No unknown-question search, semantic-recall assessment or cross-document validation was performed. Narrative still needs human judgment.

## Inspect and reproduce

`/analysis?run=analysis-9373e1c4632a063d` displays A1 pending review, experiment scope, rejected/successful calls and the full trace. FY2025 revenue opens its newly recovered source; calculations link to their inputs. A0 remains separately accessible and approved.

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_analysis.py --gap --env-file /path/to/local.env
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_cloud_analysis.py experiments/cloud_analysis/analysis-9373e1c4632a063d
```

input_snapshot is the incomplete input; resolved_snapshot is the experimental overlay. input_review approves only the parent, neither new artifact. Requests/responses, errors/corrections, evidence and answer are preserved independently.

Next: review A1. Any further expansion should separately scope genuine Document Navigator retrieval, not describe this fixed adapter as a general capability.
