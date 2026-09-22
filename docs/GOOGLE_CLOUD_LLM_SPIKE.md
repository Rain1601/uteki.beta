# Google Cloud · LLM comparison Spike

Status: candidate, pending human review. This supplements, rather than rewrites, the v0.1 rule baseline.

## Purpose

Test a narrow loop: real model reads sources → structured facts → verifiable evidence → separate comparison. Scope remains Google Cloud named offerings and FY2023–FY2025 revenue/operating income in Alphabet's FY2025 10-K. No Thesis or additional company.

## Input and execution

1. Verify the source SHA and frozen index. Select Part I Item 1 and Part II Item 8.
2. Retrieve literal Google Cloud matches plus adjacent blocks within those sections: 38 blocks, preserving matching tables in full and attaching source Inline XBRL concepts, annual contexts, units and scales.
3. Send a fixed prompt and source bundle. Neither Reference nor rule outputs are read. Request: 112,205 bytes. Provider-reported usage: 28,575 input and 847 output tokens.
4. The configured model alias was `deepseek-chat`; the returned model was `deepseek-flash`. Both are recorded. One real model response was obtained.
5. Never repair model output silently. Validate subject, duplicates, citations, numeric cells, year headers, USD scale, annual Cloud context and metric concept. Offering-name substring checks do not establish semantic completeness; human review remains necessary.
6. Publish a candidate snapshot only after validation; read Reference in a separate evaluation process. Downstream reading is still a fixed tool-call simulation, not an autonomous model loop.

## Result and validator correction

- Original model run: `run-bc134b0c276425b0`, with preserved `response.raw.json` and `output.json`.
- The first validator falsely rejected valid revenue evidence because it required the segment table's `Revenues:` heading. The model cited the revenue breakdown table on reported page 60; the rule baseline cited the segment table on page 87. Both disclose the same Cloud revenue.
- Validator v0.2 checks the source cell's Inline XBRL metric concept instead of requiring one table template. The rejection is preserved and an alternative-table regression test was added.
- Revalidation run `run-9856300a8d74fa77` replays the unchanged response after byte-equality verification of the request. It records `replayed_from`, original call time and response SHA. Zero new model calls in this replay.
- Seven records match the candidate reference: one offerings record and six metrics, zero differences. Source validation passes. The reference is pending human review and is not an independent test set; this does not establish accuracy or generalization.
- An earlier network-restricted attempt, `run-9a2f4a8962ac698d`, failed without a model response. Preparation records are also preserved; neither counts as a model evaluation.

## Inspector and provenance

`/result?view=cloud-spike` selects the latest usable candidate; prepared/failed runs cannot replace it. The `run` parameter pins a version. The inspector allows switching rule/LLM runs, preserving the split source view and numeric highlighting, with candidate-reference differences, actual input and metadata. Extraction and reading simulation are clearly distinguished. UI supports Chinese/English; source filing text remains English.

Immutable run folders hold input, request, raw response, parsed output, diagnostics and metadata; validated runs additionally hold snapshot and trace. Credentials are used only for provider authentication, not copied into the repository or saved in requests. Old runs are not overwritten.

## Reproduction and review

```sh
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --prepare-only
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --env-file /path/to/local.env
PYTHONPATH=src:. .venv/bin/python scripts/run_cloud_llm_spike.py --replay-run data/research_data/google_cloud_spike/run-bc134b0c276425b0
PYTHONPATH=src:. .venv/bin/python scripts/evaluate_cloud_spike.py data/research_data/google_cloud_spike/run-9856300a8d74fa77
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/unit -q
```

57 unit/regression tests passed. Browser inspection checked the revenue table and highlighted cell. Next human action: review the seven facts/evidence and reference scope; UI approval is not data approval.

## Limits and next step

Retrieval is fixed-section literal matching, not a completeness guarantee. Numeric validation supports this filing's layout and known concepts, not general financial parsing. One model response does not establish stability, cross-document performance or held-out performance.

Next proposed narrow Spike: an Analysis Agent autonomously reads the current tools, requests source retrieval when data is missing, and explicitly reports unresolved gaps. Keep Thesis, other companies and quarterly filings out of this iteration.
