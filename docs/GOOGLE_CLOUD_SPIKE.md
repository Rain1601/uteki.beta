# Google Cloud retrieval spike v0.1

Status: rule-baseline candidate, pending human acceptance. Chinese is normative.

Scope: only the frozen Alphabet FY2025 10-K and its Document Index. Extract named Google Cloud offerings and FY2023–FY2025 revenue and operating income presented in this filing, in USD millions. Offerings are not an inferred organizational hierarchy or exhaustive product catalog.

Method: select Part I Item 1 and Part II Item 8 by index range. Apply a sentence rule to offerings and table rules to metric groups, row labels and merged year headers. Check each value against original HTML Inline XBRL scale, USD unit, annual context and Cloud subject. Fail on missing or ambiguous inputs. No LLM is called; model/prompt are null. This does not validate LLM extraction.

Provenance and time: pin source SHA and validate index hashes. available_at uses the source manifest filing date, 2026-02-05, with date precision; it does not assert earliest public availability. Comparative years reflect this filing's presentation and cannot simulate what was known in FY2023. Preserve run time, code hash, index ID, selected node IDs and fact snapshot.

Acceptance: compare seven records (one composition, six metrics) against a source-reviewed Reference candidate, pending human review before Gold. Check subject, period, unit, value and location. Neither extractor nor simulator reads Reference. Rules and Reference were developed against the same source; agreement is not generalization evidence.

Retrieval: manifest returns coverage only; facts filters by field/period with pagination; evidence resolves fact_id to table cells and year headers; request_missing only records requests without an acquisition worker. Capture arguments and full responses. Empty results distinguish not_extracted/unsupported, never undisclosed. Loading files inside the service is not loading them into model context.

UI: /result?view=cloud-spike shows this independent run's facts, original-layout excerpts, retrieval trace and source identity. It does not replace the full business candidate or produce a Thesis.

Run: PYTHONPATH=src .venv/bin/python scripts/run_cloud_spike.py. Each execution creates a new run directory. Tests in tests/unit/test_cloud_spike.py read Reference only on the evaluation side.

Next candidates: human review of data and interactions; LLM extraction on the same scope; document navigation retrieval and fault-injection tests. Additional companies, 10-Q, a general Fact Store and Thesis remain separate spikes.
