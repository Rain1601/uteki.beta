# Research archive v1.1 · Independent researcher streams

2026-09-14. Chinese counterpart: RESEARCH_WORKSPACE_V1.1.zh-CN.md. Supersedes v1.0's shared adoption slot, archive-before-replace sequence, and automatic archival of peer candidates.

## Backend contract

- Unique effective slot: company + researcher_id + scope + primary document. Year is presentation only; quarterly filings stay distinct.
- researcher_id identifies a stable strategy, not mode, model or prompt version. The two inspected open-drivers experiments map to single-default / team-a. Unidentified historical strategies remain unassigned and cannot be adopted or inherited.
- Runs enter through seed as candidates, never overwrite history. config_version is the manifest hash; source paths and artifact hashes remain. New teams should declare id/label per mode in manifest.researchers; a generic team mode is insufficient for identity.
- adopted is the sole effective state. No duplicate current pointer is maintained.
- Replacement requires replace_snapshot_id, replace_revision and expected_slot_revision. The slot token hashes every member's ID, revision and status, detecting intervening adopt/archive cycles. One locked commit archives the old effective version, records replaced_by_snapshot_id and adopts the new one. Other candidates stay pending.
- Reject requires a reason; reconsider returns a rejected candidate for review, never directly adopts it. Archive/delete/restore do not auto-promote successors. Evidence checks and explicit inferred-primary confirmation remain mandatory.
- Editing an effective, candidate, archived or rejected report creates a new candidate without changing source content. Save parent_snapshot_id, edited_at, author, reason and edit_diff; retain the original model run timestamp. Reset validation to pending and remove prior review signatures.
- The editor changes existing claim text, limitations and findings. Claim count/order, citation objects and other schema fields are immutable. Adding/removing claims or changing evidence belongs to a later evidence-repair workflow. Human review cannot override failed source validation.
- Opinions are not copied implicitly; underlines stay on their original snapshot. Decision history and before/after revisions are available. Reading-annotation audit is not included in research context.

## Context

- Store.context / build_context accept researcher_id. Legacy omission is allowed only when exactly one identified researcher exists; otherwise explicit selection is required.
- Select adopted content by company, researcher, scope and time. Load one latest eligible baseline and a directory of older eligible history. Reject pending, rejected, archived, deleted and unassigned content.
- History access and opinion-source membership recheck researcher identity server-side. New frozen manifests use schema 1.1 and include researcher identity. Old files remain immutable; identity-free legacy history is not silently upgraded.
- Upstream replacement/withdrawal flags descendants without invalidating or rerunning them. New contexts carry the notice; frozen execution inputs remain unchanged.
- This release implements context selection, freezing and history access, not real model execution or semantic re-review of opinions. No paid calls.

## Migration

Store.migrate_researchers(identities, dry_run=True) previews mappings. Commit checks the source is unchanged under a lock, writes a byte-exact SHA-named .bak, then atomically publishes schema 1.1 and a mapping audit. Preserve IDs, content, statuses, comments, underlines and prior events. Human descendants inherit confirmed parent identity; unknowns are quarantined. Duplicate effective slots or cyclic lineage abort. Repeated migration is a no-op.

Startup performs this idempotent migration before idempotent experiment import, without adoption. Rollback requires stopping the service and using matching backup/old code; never overwrite new user records with a stale backup.

## Minimal UI

Researcher and scope selectors; one timeline row per source. Prefer the effective report; otherwise explicitly preview a candidate. Pending/history lists are collapsed. Legacy snapshot URLs infer researcher; explicit filter mismatch cannot display foreign content. URLs preserve filters and version. Companies, Data Agent originals, source drawer and Chinese helper translations remain intact.

Verification: tests/unit/test_researcher_streams.py plus archive/context/routes/underline regression. Browser writes use an isolated temporary archive, never test-adopt real user records.
