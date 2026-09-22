# Uteki working agreements

## No implicit business scope or sample-specific fallbacks

- Shared contracts, parsers, prompts, query services, and production entry points
  must not hardcode a company/entity, reporting period, source/snapshot, local
  experiment path, or expected financial result as a default or fallback.
  Required business scope comes from validated caller input, source metadata,
  or an explicitly selected, versioned configuration/adapter. Moving the same
  implicit default into a constant or config file does not satisfy this rule.
- Missing, blank, unknown, conflicting, or unsupported scope must produce a
  validation error or an explicit gap. Never substitute Alphabet, the first
  available source, the latest period, or a sample value to make a run succeed.
- Derive discoverable entities and coverage from the selected dataset. Apply
  company/entity, period, source policy, cutoff, and candidate/adoption scope
  consistently to queries, calculations, evidence, and missing-data diagnostics.
  Another company's source cannot establish coverage for the requested company.
- Company/taxonomy mappings belong in named adapters with explicit selection
  and validated issuer/source scope. Literal, sample-specific semantic repairs
  must be isolated from reusable execution code and pinned to reviewed source
  and input hashes. Do not present these repairs as general extraction ability.
- Fixtures, experiment runners, and examples may contain concrete companies,
  dates and paths when their scope is explicit. Expected answers stay in tests
  or evaluation artifacts and must never feed extraction/normalization logic.
  Preserve historical snapshots; publish schema/config changes in a new run.
- Stable protocol enums, documented formulas, units, provider endpoints, and
  resource limits are allowed constants. Business-dependent assumptions such as
  fiscal calendars and currencies must be explicit supported capabilities;
  reject unsupported inputs instead of silently reinterpreting them.
- Review all callers and exported schemas when changing scope requirements.
  For behavior changes, test missing scope, another company/source, another
  period where supported, and no fallback/cross-company evidence. Use a small
  independent synthetic dataset as well as the original pilot; passing only the
  Alphabet example is insufficient evidence of reusable behavior.
- Report review coverage and remaining adapter limitations honestly. Do not
  claim full multi-company support merely because a default was removed.

## Frontend design

For frontend styling, layout, new pages, and interaction design, read and apply
`~/.codex/skills/frontend-design/SKILL.md` before making changes (expand `~` to
the current user's home directory). Official source:
https://github.com/anthropics/skills/tree/main/skills/frontend-design.
This is a user-supplied skill; if unavailable, ask for its location rather than
pretending it was applied. Preserve the approved product behavior and real data.

Create a compact visual plan, review it against the specific research workflow,
then implement and visually verify. Keep the companies list unchanged unless
the user explicitly includes it. Keep UI bilingual, evidence traceable, and
snapshot/adoption rules intact. No model calls or deployment for styling work.

Record meaningful design choices and checks in `docs/FRONTEND_DESIGN.md`.

## Uteki interface baseline

For Uteki interface work, read `skills/uteki-interface/SKILL.md` and its linked style guide first. It records the agreed company-first, single-window, trackpad-first design rules. Reuse this baseline rather than inventing a new style each turn. Latest explicit user feedback takes precedence. The guide is a baseline, not a claim that current pages passed visual review.
