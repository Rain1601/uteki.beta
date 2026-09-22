# Uteki · Evaluation and Company Research Archive v1.0

Update 2026-09-14: adoption, replacement, editing and researcher-context rules are superseded by [v1.1](RESEARCH_WORKSPACE_V1.1.md). This document retains the original decisions as history.

Status: rules confirmed by the user; V1-A/V1-B foundations implemented; model inheritance and quality acceptance remain next-stage work. Date: 2026-09-13.
Chinese counterpart: RESEARCH_WORKSPACE_V1.zh-CN.md. Keep sections and rule IDs aligned.

## 1. Scope and ownership

Build a traceable, revisable company archive: what we believe, why, what new evidence changes, and when to acknowledge uncertainty or invalidation.

Alphabet only. Retain Single and Team without assuming a winner. Assistant proposes evaluation standards; user reviews them and owns interaction design. Implement confirmed rules only. The old product is a visual reference, not a source of migrated facts, conclusions or architecture. Keep the companies list unchanged.

No trading, position changes, scheduled monitoring, new-company acquisition, database or frontend framework. Implement confirmed rules only; no new paid model calls. Keep source facts separate from analytical judgments.

## 2. Question and output

Development question: What are Alphabet's most important growth drivers and downside risks over 3–5 years? Which business changes affect value, and what is missing to assess share-price implications?

The user-endorsed Cloud growth/margin improvement plus resilient AI search/advertising statement is a candidate hypothesis, not ground truth. Do not inject it into independent tests. Separate scale, growth rate, absolute increment, economic return and market expectations. Rankings are inferences.

Outputs: direct answer, key hypotheses, supporting/opposing evidence, unknowns, verification plan and baseline-relative changes. Thesis/Drivers/Risks/To Watch is optional presentation, not an attributed master framework or mandatory buy thesis.

## 3. Evaluation protocol

### E1 Freeze before running

Record question version, document/index SHAs, primary document, publication times, information cutoff, prompt/code/model/provider versions, upstream routing uncertainty, tool/token/time budgets, context manifest and comment versions. Never overwrite old experiments.

Offline contract tests first; paid comparisons after approval. Repeat the development case three times per mode, reporting every run including failures; do not claim statistical significance. Prepare two held-out questions controlled by the user or an independent reviewer; run after protocol freeze and retire used holdouts into development. A question known to the assistant is not hidden from it.

### E2 Three distinct layers

1. Evidence: source existence, successful reading, version/time, source binding, table units/periods/coordinates. Provenance is not semantic support.
2. Reasoning: future drivers rather than current scale, increment and economic mechanism, fact/inference separation, counterevidence, actionable verification, value versus price expectations.
3. Realization: freeze hypotheses and update on future disclosures. Historical replay tests process, not uncontaminated forecasting; models may know future outcomes. Rising prices do not prove a thesis.

### E3 Review method

Calibrate with existing real outputs and 2–3 positive/negative examples before rerunning. Execution completeness and context discipline are separate gates. User utility (preference, readability, review time) is separate from factual correctness. Record error type, severity, distinct root cause and citation occurrences; repeated citations are not independent errors.

Pass/partial/fail/undetermined per applicable criterion, with explanation and references. Report applicable denominators, coverage gaps, critical errors and cost/latency distributions, not an opaque aggregate score. Justified abstention can be correct.

Blind human review hides mode/model/cost and randomizes presentation; assess quality before revealing cost. Content may reveal identity, so blinding is imperfect. User preferences govern usefulness, not factual truth. Add a second independent reviewer for important/disputed judgments when available; label single-reviewer judgments honestly. LLM judges assist rather than adjudicate.

Record success, failure, cancellation and budget refusal. Unknown cost is not zero. Separate real-product budgets from equal-budget comparisons. Multiple simultaneous changes cannot establish single-variable causality.

### E4 Gates and regressions

Before acceptability review: no unread/nonexistent citations, wrong primary/cutoff, or unflagged critical numeric/semantic contradiction. Mechanical success means eligible for human review, not correct research.

User reviews substantive reasoning. Preserve failures and difficult cases. Regressions include ranking future drivers solely by size, confusing disclosure additions with business inception, counting AI mentions as contribution, treating user opinion as fact, and predicting prices without expectations evidence.

## 4. Company page and evidence interaction

P1: Keep /companies. Two main tabs at /companies/alphabet are confirmed: Research archive and Company data. Persist tab/snapshot selection in shareable URLs.

P2: Research uses a left snapshot timeline and right selected result. Prioritize current judgment, baseline changes, hypotheses/evidence, unknowns, verification and comments; logs/costs are secondary disclosures. Dense, restrained bilingual UI; do not copy the old sidebar/company pool.

P3: Company data covers sources, structured facts and semantic outputs. Main interaction is extracted field/business node ↔ source: click name, description, number or relation to locate evidence on the right. Multiple sources have numbered previews; preserve selection across views. Keep year, unit and row/column context. Translations are aids; English source remains canonical.

P4: Retain Document Index as a secondary outline/debugging view within document detail; preserve deep links. Documents without semantic outputs say indexed-only, never borrow another filing's results.

## 5. Snapshots, clocks and states

S1: Raw runs are immutable. Editing creates a revision with parent, diff, author and timestamp; only unaccepted revisions are editable. Accepted versions cannot be edited. After archiving, edits still create a revision rather than rewriting history.

S2: Sort by primary document public availability descending, not period end; within a document by run start descending, then unique ID. Display minute-resolution versions in Asia/Shanghai, disambiguated by a short ID; retain precise UTC time and unique run_id. Declare the primary document before running, including for multi-document analyses; list every secondary source.

S3: Separately store the knowledge cutoff covering every permitted source and inherited item's availability. A primary date cannot disguise newer information. Uncertain publication dates exclude material from strict point-in-time replay.

S4 (scope rule confirmed): Acceptance key is company + research_scope + primary_document_id. At most one accepted revision. Single/Team compete for the same slot; model/index changes do not create extra slots. Explicit acceptance archives competing candidates atomically and reports transitions. Never silently replace an existing accepted snapshot; archive it first. Enforce uniqueness atomically against concurrent actions.

Transitions: unaccepted→accepted/archived/deleted; accepted→archived; archived→accepted (uniqueness checked)/deleted. Unaccepted/archived versions may spawn edits. Propose recoverable soft deletion, excluded from context; archive an accepted version before deleting. Permanent purge is out of v1 scope.

S5: Accepted is not true, archived is not false, deletion does not erase past execution. Append actor/reason/before/after events. Historical context manifests never change retroactively; state changes affect future context construction.

## 6. Context and human comments

C1 (confirmed): Use the latest eligible accepted snapshot in the same scope as baseline, retrieving older accepted history on demand rather than concatenating all reports. Both knowledge cutoff and comment availability must be eligible. Distinguish strict historical replay, today's retrospective research and live tracking. Historical access respects current adoption status; default research tools exclude archived content.

C2: Default tools expose only currently eligible accepted analyses. Unaccepted/deleted/archived reports are not auto-loaded; historical audit requires explicit separate selection. Freeze context at run start; if baseline state changes mid-run, preserve execution and flag the change afterwards.

C3: Removing an ancestor cannot erase inherited conclusions already present in descendants. Track lineage, flag affected descendants for review and communicate retractions next run; do not claim models can forget consumed content.

C4: Comments attach to snapshots and have independent versions. Preserve original text; distinguish preferences, factual assertions and hypotheses, with suggested classifications confirmed when ambiguous. Propose an explicit carry-forward switch, limited to accepted snapshots; archiving/deletion stops inheritance but preserves audit. Persistent cross-snapshot preferences need a separate opt-in, off by default.

C5: Reassess inherited comments each run: preference/supported/challenged/unverifiable/outside scope, with reasons and sources. For “Services matters more,” clarify dimension and horizon rather than accepting it as fact or declaring the user wrong merely for disagreeing. Preferences cannot override evidence, suppress counterevidence or bypass cutoff rules.

Guarantee explicit review status and grounds, not infallible detection of human error. Unchecked opinions must say not reviewed this run, not verified; such substantive claims cannot silently support new conclusions.

C6: Log inclusion/exclusion reasons, token budget and unloaded items. Use summaries with references and explicit pagination, never silent truncation. Output which human opinions were accepted, rejected or left unresolved and why.

## 7. Change and tracking

Stable hypothesis_id links statements across runs. Store statement, business scope, horizon, evidence/counterevidence, observables, reconsideration conditions, state and update time.

Compare against explicit baseline_snapshot_id: new/strengthened/weakened/invalidated/still unknown/no longer covered. Attribute changes to new evidence, interpretation, human edits or model/prompt changes. Rerunning the same material with another model is not a business change. No baseline means first research, not a fabricated diff.

An unresolved unknown or absent counterexample does not imply confirmation. Thresholds need business justification. Future updates require review and never trigger automatic trading.

## 8. Phases and acceptance

V1-A: Confirm bilingual rules; offline tests for states, eligibility, chronology, same-minute collisions, concurrent acceptance, restore, opinion classification and ancestor retraction.

V1-B: Integrate existing real outputs into the company archive/data areas and source-time timeline with dual-pane evidence. Regress companies, /result, index and experiment deep links. Do not copy old facts/data.

V1-C: Minimal frozen Single/Team comparison, paid budget approved first. Preserve old outputs; user preference is not ground truth.

V1-D: One new-material hypothesis update and one incorrect-human-opinion stress test. Verify conflict warnings and immutable originals. UI and research quality are separate acceptance tracks.

## 9. Confirmed decisions

Confirmed: latest accepted plus on-demand history; scope-specific acceptance uniqueness; proposal review before implementation.

Additionally confirmed: soft deletion, revision-based edits, two main tabs, explicit carry-forward comments and behavior after archiving. A new model run still requires a separate budget confirmation.

## 10. Current delivery and remaining gaps

Implemented: two company tabs, four historical candidates, atomic state and audit persistence, derived edits and review, versioned comments and withdrawal, context eligibility and immutable manifests, restricted history reads, and an in-page source drawer with exact block highlighting. Historical primary sources are explicitly inferred from successful read counts and require confirmation on adoption. Original model outputs remain unchanged.

Remaining: connect the context adapter to real Analysis Agent execution, model re-review of opinions, stable hypothesis IDs and semantic change generation, and full company-data split-pane integration. Company data currently reuses real material listings and existing business/Cloud output entrances; it does not imply all filings have semantic extractions. Historical experiments have no baseline and show that explicitly, without fabricated changes. No new model calls or automatic adoptions in this delivery.

## 11. Interaction acceptance examples (proposed, not executed)

### A. Adopting one of two candidates

Single A and Team B share a primary document and research scope. Adopting A previews validation and the consequence that B will be archived. On confirmation, A is adopted and B archived; A alone is the next default baseline. Model/parser versions do not create another slot.

The actual v0.2 Single still has one unread citation. Users may endorse its reasoning or comment, but cannot label it validated. Create an evidence repair or human revision first, then adopt the exact revision; preference cannot bypass provenance failures.

### B. Editing and replacement

Adopted A has no direct edit action. Archive A to release its slot, then adopt B or derive human revision A-r2. Preserve the model original. Restoring a deleted record should restore it as archived, never automatically adopted, avoiding conflict with the current choice.

### C. Human opinion propagation

On A, the user writes “Focus more on Cloud's future increment than current revenue size.” Preserve the text, suggest research preference classification and explicitly carry forward by comment ID/version in B's context manifest. B must still independently examine Cloud evidence.

If the user writes “Cloud revenue exceeded Services in 2025,” flag a factual conflict using the year-specific table; do not silently change numbers. If “Services matters more,” clarify current profit, future increment or downside exposure rather than automatically declaring error.

To prevent opinions disappearing when the latest baseline changes, inherited reviews retain original comment_id. Once B is adopted, it may carry references to still-active selected opinions, not copy them as unsourced facts. Retracting the original flags all descendants for review and stops future automatic propagation; historical execution manifests remain immutable. This rule is confirmed.

### D. Timeline and historical boundaries

A/B for the same FY2024 10-K share the document's publication-time group, sorted within it by actual execution time. If A reads later quarterly filings, it stays in its primary-material group but explicitly displays the newer information cutoff and retrospective label.

Strict point-in-time tools exclude later materials, opinions and historical results. Later-created research cannot pretend to have existed then. If no eligible baseline exists, start from source material and label no baseline.

### E. Reviewing new evidence

The new snapshot explicitly compares against A. When evidence challenges H1, show old/new judgments, reason and evidence on both sides. Model wording changes are interpretation changes; not investigating H1 means not covered, not invalidated. Review should make clear what changed, why, and whether the user agrees.

### F. Data and evidence

Selecting an extracted field opens and highlights its document on the right. If another citation belongs to another filing, visibly switch title/version, not merely scroll. Returning from index inspection preserves selected document/field/citation. Indexed-only materials do not pretend to have semantic outputs.

### G. Separate functional and analytical acceptance

Offline checks: concurrent adoption never creates two active adopted records; restore does not restore context permission; mid-run state changes are flagged; reads and rejections are auditable.

Analytical checks: anonymously compare original answers to the same question. Well-supported Cloud-first or Services-first conclusions may pass; evaluate evidence and reasoning rather than ranking. Incorrect-opinion stress tests do not reward automatic disagreement with users.
