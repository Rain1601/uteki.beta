# Company notebook · 2026-09-18

User selected the company notebook demo. This direction supersedes the earlier
blue-gray palette. Applied the official Anthropic frontend-design skill installed
at ~/.codex/skills/frontend-design/SKILL.md; original license retained.

Plan: paper #FCFBF9, reading surface #FFFFFF, ink #30312F, muted #71716B,
divider #E6E3DE, accent #8A7053. Georgia for the wordmark and company identity;
Avenir Next / PingFang SC for bilingual reading and controls. Dark ink actions,
bronze links and selection markers; semantic warnings remain distinct.

Layout: left aligned research with a white reading surface and quiet paper margins.

```
Global navigation / company identity
Research sections
Researcher index | continuous report | materials and version history
```

Brief review: preserve the selected notebook's calm reading hierarchy without
copying demo-only chapters, fake team events or decorative numbering. Home remains
an attention queue; structured data remains a table. Companies retain their current
list layout. Reading, review and adoption remain separate, and source documents
remain unthemed. Existing responsive layouts and reduced-motion support are retained.
Shared tokens replace old blue selections, with scoped workspace rules for embedded
page styles. No data, model output, routes or review logic changed.

Verification: 241 Python checks and 7 JavaScript checks passed. Browser inspection
used the production renderers with isolated, explicitly labeled fixture data:
desktop company overview, report directory and report reader; 390px report,
structured table, materials and attention dashboard. Report and data pages had
390px document width with no page-level overflow. Financial tables scroll within
their container. Verified bilingual switching and the daily-viewed checkbox;
the pending-review label remains after marking viewed. Fixed nested support labels
that previously displayed both languages. Reset viewport after inspection.

Limitations: the original complete data/ and experiments/ inputs remain unavailable.
The temporary preview does not implement research mutation or annotation APIs
(the reader correctly reports unavailable annotations); evidence integrity and
review behavior were covered by existing offline tests, not full live-data browser
acceptance. Source documents and legacy experiment pages were not visually checked
in this pass. No model calls or deployment.

---

# Research archive visual direction

## Independent annual narrative · 2026-09-15

Applied frontend-design to the actual Single Agent candidate reading page. Reuse
white #FFFFFF, ink #243347, secondary #68768A, blue #285DB0 and soft #F7F9FC;
Avenir Next/PingFang SC, left-aligned continuous prose with a sticky 220px contents
rail and a mobile horizontal contents list. No dashboard cards or decorative
metrics. Preserve model titles and paragraphs, even when verbose: this is an output
review, not editorial correction. Cap visible source links at three and retain
ellipsis/hover quotes; unread references explicitly say unverified. Fold call
purposes and per-call cost records below the report. Browser screenshot verified
desktop spacing and successful local route rendering. Runner's three tests pass.
Only report generation used the model; presentation involved no additional calls.

## Researcher streams · 2026-09-14

Backend-first change. Preserve white #FFFFFF, navigation #F5F7FA, ink #202B3B,
secondary #596779 and blue #275DAD; keep Avenir Next/PingFang SC. One material row
per selected researcher/scope, left aligned; candidates and immutable history fold
into the report rather than multiplying sidebar cards. Native selects and existing
dialogs are sufficient; no new visual system or company-list redesign. Review
against brief: identity separation belongs on the server, not just a UI filter.

Verification: 197 offline tests passed, including researcher isolation, concurrent
replacement, migration preservation and HTTP review/replacement. Browser QA used
an isolated archive for adoption and editing; confirmed researcher switching,
one material row, pending revision text and the original remaining effective.
The production archive migration preserved all four snapshots and their statuses,
comments and underlines with a byte-exact backup. Production screenshot verified
the selector and unchanged evidence-failure gate. No paid model calls.

## Reading underlines · 2026-09-13

Keep the quiet white/blue-gray workspace, existing Avenir/PingFang type, and no
additional permanent panel. Selected claim text reveals a compact floating action;
saved marks use a thin amber underline, not a large filled card. Clicking an
underline offers removal. Keyboard selection and Enter on a saved mark work too.

Reading marks are not opinions, adoption decisions or source annotations. Store
them separately from snapshot contents, with independent revision checks, Unicode
code-point offsets, exact quote and claim hash verification. Keep creation/removal
timestamps in the audit history; never inherit marks into another snapshot or
analysis context. No model calls. D0 supports one claim paragraph per selection;
overlapping marks are rejected with an explanation. Deleted snapshots are read-only.

Verification: 182 tests passed. Browser QA on an isolated archive confirmed Chinese
text selection, save, persistence after reload, removal and persistence of removal.
Fixed a collapsed-selection event that prematurely dismissed the removal toolbar.
The production-local page was reloaded to confirm the annotation entry point; no
test marks were written into the user's archive.

## Unified workbench · 2026-09-13

Scope now explicitly includes the companies list and all local workbench page
families: archive, data inventory/status, navigator, business result, Cloud views,
and served experiments. Raw SEC source pages and iframe documents are excluded.

Tokens: white #FFFFFF, navigation #F5F7FA, ink #202B3B, secondary #596779,
interaction blue #275DAD, warning #85531E. Avenir Next / PingFang SC throughout.
Layout stays left aligned: navigation, quiet filters, continuous content. Use
spacing and subtle hover/selection backgrounds rather than boxes and ruled cards.
Keep borders where they encode actual financial table cells or focus affordances.

Review against brief: no terminal restyle, decorative hero, wholesale route
redesign or animation on every row. Existing snapshot, search, filter, pagination,
translation and evidence behavior stays intact. A shared presentation module/CSS
is applied explicitly to renderers, never to source renderers. Archived experiment
files remain immutable; the served presentation receives the style at runtime.
Transitions are 140ms on controls; user-triggered drawers/previews reveal over
160ms. Reduced-motion preference disables both. Desktop archive remains two
independently scrolling panes. Narrow readers stack without horizontal page overflow.

Verification: 169 tests passed. Desktop visual inspection covered companies,
research archive, data inventory, document navigator, business map, Cloud data,
Cloud analysis and served experiment comparison. Search and pagination, node
selection, original-layout switch and table-cell evidence navigation were checked.
The browser viewport override did not change actual viewport dimensions, so mobile
CSS is implemented but not claimed as visually verified; override was reset.

## Chinese evidence reading · 2026-09-13

Preserve the existing palette, typography, fixed rail and compact citation row.
Chinese mode uses a short translated excerpt; focus/hover shows the complete
Chinese translation followed by the unchanged English quote. English mode shows
English. Exact normalized quote matches select a versioned presentation-only
translation catalog, not source block IDs or fuzzy matches. No source snapshot,
model answer, evidence URL or validation flag is changed. Translations are
assistant-authored, explicitly pending human review, not official filing text.
Unmatched new quotes show a missing-translation label and English fallback.
No paid model calls. SEC source document remains unchanged in the evidence drawer.

## Compact evidence previews · 2026-09-13

Keep the existing six-color palette and Avenir Next/PingFang type. Replace long
multi-line citations with one-line excerpts capped at 28ch visually, alongside
the unchanged material badge. Preserve first-three disclosure and ellipses.
Hover or keyboard focus opens a readable full recorded quote; click still opens
the original source. The preview is viewport-constrained, scrollable, hoverable
and dismissible with Escape. Mobile uses the same direct source link.
Review: compact evidence supports reading the judgment, without replacing useful
words with IDs. No invented Chinese translation, model call or answer rewrite.

Validation: 18 UI/route tests passed; inspected the requested team snapshot in
the browser. Keyboard focus revealed all 618 characters of its first citation,
Escape dismissed the preview, and clicking still opened the anchored source.

## Fixed snapshot rail · 2026-09-13

Keep the approved paper/rail/ink/secondary/blue/warning colors and Avenir Next /
PingFang typography. Only change scrolling: company header and tabs stay in place,
with a fixed-height workspace beneath them. The left snapshot list and right
research document scroll independently. Use viewport flex/grid layout rather than
hard-coded fixed offsets so bilingual text, feedback and the evidence drawer fit.
On phones, retain the compact stacked list and normal document scroll.

Brief review: this preserves the researcher's place in the snapshot timeline while
reading long evidence-backed results; no new panels, decoration or data changes.

Validation: 17 UI/route tests passed. Browser scroll check moved the research pane
1,928px while the snapshot rail stayed at scrollTop 0 and the same viewport top;
header and company tabs remained visible. Screenshot reviewed after scrolling.

## Citation disclosure · 2026-09-13

Keep the existing palette, type and left-aligned evidence sentence. Show the first
three distinct references per claim; an inline bilingual Show more/Show less button
reveals the rest in place. Each claim controls its own disclosure. Preserve long
excerpt ellipses and all source links; this is presentation only. Keyboard focus
stays on the toggle and aria-expanded/aria-controls describe its state.

## Content-first citations · 2026-09-13

User correction: source links must read as evidence, not opaque IDs or numbered
buttons. Keep existing paper/rail/ink/secondary/blue/warning tokens and typography.
Each claim is followed by a left-aligned sentence: Based on [recorded excerpt]
[2025 10-K]; [another excerpt] [2026 Q2 10-Q]. The words open the original source.
The material tag uses the report period, never the filing year; unknown metadata
stays explicit. Source drawer captions show material and content instead of IDs.

No generated summaries or numbers: the recorded quote supplies the link text,
with an explicit ellipsis for long excerpts. Images without text stay labeled as
chart data with no excerpt. Failed-citation warnings remain; rendering does not
certify model quotes. Exact duplicate references collapse only in the display.
No model answers, original citations, or archive states are rewritten.

## 2026-09-13 · frontend-design first application

Audience: one researcher comparing time-versioned company judgments with source evidence.
The page is a reading and review tool, not a promotional dashboard.

Tokens: paper #FFFFFF; navigation #F1F4F8; ink #202B3B; secondary #566477;
interaction #275DAD; warning #85531E. Borders derive from the navigation palette.
Type: Avenir Next with PingFang SC/Microsoft YaHei fallbacks for interface text;
the same family for headings and reading. No downloaded font dependencies.
Numbers use tabular figures, not decorative monospace. Body line length <=76ch.

Layout: left-aligned, compact source/version rail and a readable continuous research
column. Opening evidence gives the source its own right column on wide screens;
on smaller screens it is an explicit closable overlay.

```text
Company identity                  Language
Research archive | Company data
Source / run rail | Question and provenance      | Source (on demand)
                 | Claims + evidence references |
                 | Changes, gaps, human review  |
```

Review against brief: a dark finance terminal or serif newspaper would be generic
here and harder to read for long bilingual claims. Use a quiet document workspace.
The distinctive focus is the selected source/version rail paired with precise
evidence, not color decoration. Remove decorative claim numbers; keep citation
numbers because they identify multiple sources. Fold pilot/provenance explanations
into a disclosure while leaving failed-validation warnings visible.

Scope: archive styling and company-data visual consistency only. No companies-list
redesign, altered model answers, adoption semantics, new model runs, or publishing.

Validation: 18 focused UI/route/data tests passed. Browser inspection covered the
desktop view, Chinese/English chrome, exact source highlight, and narrow layout
(390px override; 375px content viewport with no horizontal page overflow).
The viewport override was reset. Original model text and failed-citation state remain.

Skill installation: user-supplied body preserved at the local skill path. Removed
the frontmatter reference to an absent LICENSE.txt; no license terms were invented.
The bundled validator could not run because PyYAML is absent; frontmatter was
manually reviewed and file content compared against the supplied text.

## Earnings P0 reader / 2026-09-15

Apply the existing frontend-design system, not a new dashboard. Palette: paper
#ffffff, ink #202b3b, secondary #566477, evidence blue #275dad, selection #f1f5fb,
PDF evidence marker #bd8c21. Keep Avenir Next/PingFang SC for controls and text.
Left-aligned continuous transcript, expandable speaker/exchange sections, with a
sticky original-PDF page on the right. Native source typography stays intact in
PDF renders. Original English is explicit; controls are bilingual.

```text
Material type / year filters (existing company data page)
Call title and provenance
Prepared remarks | Q&A | Closing | Search
Readable turns and questions | Original PDF page + exact region highlight
```

Brief review: avoid report cards, new company navigation or artificial paragraph
tiles. Each click answers “where was this said?”; the source page is the primary
visual. No autonomous animation, visible keyboard focus, single-column narrow
layout. Company list and adoption/snapshot rules unchanged.

Verification: 205 tests passed. Browser verified native material filtering,
English/Chinese controls, call search, PDF p.14 selection/highlight, release
original tables, and 390px layout. Original page dimensions drive the overlay;
hide both old image and highlight while a new page is loading. Viewport reset.

## Researcher rail and annual baseline / 2026-09-15

Second review: keep the three-column layout. Right rail uses plain material headings with indented timestamp/version rows and a status filter, not tinted cards. Move candidate/history/audit disclosures out of the central report into the right rail. Palette and Avenir Next/PingFang remain unchanged. Selected text opens a compact note dialog; existing underlines remain and can receive notes. Review against brief: navigation belongs in the rail, research and anchored feedback in the center. No automatic model invocation.

Verified selected-text drag → feedback dialog → editable textarea → cancel in the real browser, without saving test text to the user's report. Backend tests cover atomic note save, edits, withdrawal, stale conflicts and rerun input freezing. Full suite: 222 passed, including offline model-stage input tests; no paid model requests.

Follow-up correction: the materials are a separate **right sidebar**, not a list above the report. Desktop wireframe: Agent list | report | material list. Both rails scroll independently; a narrow screen stacks navigation before the report. Keep paper #ffffff, rail #f4f7fb, ink #202b3b, muted #566477 and blue #275dad, with Avenir Next/PingFang SC. This corrects placement only, with no backend or report changes.

Verified in the local browser: Single Agent ↔ Team A filters material rows; material selection opens its report; ZH/EN controls work; evidence drawer opens and closes with its original source URL. Desktop and 390px layouts checked, viewport restored. Existing reports and user decisions were not changed.

Plan: retain paper #ffffff, ink #202b3b, muted #566477, blue #275dad and rail
#f4f7fb. Avenir Next/PingFang SC remain the reading/control family. Fixed-width
Agent/Team rail left; on the right a compact material/report list followed by the
selected report. Left aligned, no empty reserved evidence column until opened.

```text
Agent / Team list | Research topic + material/report list
Single Agent     | 2025 10-K   Annual research    Effective / Pending
Team A           | 2024 10-K   Annual research    Effective / Pending
                 | Selected report, sources, review and revision controls
```

Review: researcher identity must be visible, not hidden in a dropdown. Materials
belong in the right workspace; keep history collapsed within the selected material
and preserve one effective result. A wide empty status/evidence rail is not useful:
move status beside the report title and size text naturally. No company-list or
company-data redesign, no fake quarterly/peer analyses. Annual research establishes
hypotheses; supplemental analyses primarily test them, without automatic adoption.

## Codex sequential hypothesis MVP / 2026-09-15

Applied frontend-design to a separate review artifact, not the company workspace.
Visual plan: paper #ffffff, ink #233249, muted #65758b, blue #285db0,
evidence surface #f2f6fb. Avenir Next/PingFang SC; left-aligned continuous
research with a sticky three-stage navigation, one comparison table, and a
source dialog opened only on demand. No dashboard cards or auto-approval controls.
Review against brief: prioritize how a hypothesis changes, not a list of facts;
use semantic Chinese links with material labels, first three visible and the
remainder under More. Bilingual navigation; research Chinese and sources English.

Browser verification: stage links, Q2 segment-table evidence in the original
SEC HTML with visible highlight, dialog closure, and 390px body without horizontal
overflow (table independently scrollable). Temporary viewport restored. A rounding
correction is visible and links to an addendum; frozen research is not overwritten.
All source/answer/read hashes and original DOM quotes are checked by the artifact
validator. No company snapshots, decisions, or adopted contexts were changed.

## Annual revision interaction demo / 2026-09-15

Applied frontend-design to revision-demo.html using the three frozen real research
reports from the sequential hypothesis experiment. Plan: continuous white reading
surface, sticky report/version rail, semantic Chinese evidence links with period
labels, first three references visible, and a two-column before/after editor.
Palette: #ffffff paper, #233249 ink, #65758b secondary, #285db0 action,
#f2f6fb comparison surface. Namespaced CSS variables prevent shared-theme clashes.

Interaction review: Q1 suggestion -> human judgment/test/reason -> candidate ->
explicit demo adoption. Annual originals and Q1/Q2 answers stay immutable. Q2
becomes stale after adoption; no new Q2 output is simulated. The input preview
excludes unadopted drafts, old Q2 answers and old Q2 review opinions. Q1 remains
the historical basis of the revision, avoiding a circular dependency. This is
retrospective review, not a blind historical test or autonomous fact checking.

Verified in browser: candidate versus active distinction, explicit confirmation,
preserved v1 and active v2 after reload, Q2 stale message, before/after content,
context preview, and Q1 source-table highlight. 390px viewport has no body overflow;
temporary viewport restored. A test-labelled v2 is left for review in this browser.
Seven state tests and all 228 existing Python tests pass. State exists only in
browser storage with export; no formal archive mutations or model calls. Q2-based
editing and real re-execution are deliberately outside this demo.

## Annual-only reading view / 2026-09-15

User requested returning to the initial 10-K thesis, without quarterly results or
revision workflow. Plan/review: retain white paper, Avenir Next/PingFang and blue
evidence links; reserve #089981 green and #f23645 red for numeric sign, with explicit
plus/minus rather than relying on color alone. Put the plain-language thesis first,
then its three supporting questions, and annual-only metrics last. Label Search &
other as part of Services instead of implying parallel segments. No added dashboard
cards. The display rewrite preserves original answers and introduces no new research.

Added annual-report.html; original comparison remains available with signed colors.
Browser verified single-period metrics, green positive values and clear nested label.
Tests check annual-only citations, absence of quarterly result sections, preserved
original title, and red negative values in the comparison page.

## Five-part owner-oriented annual report / 2026-09-15

Plan reviewed against the user's brief: research should read as an argument about
the business, not a repeated validation form. Use a 210px quiet sticky contents rail,
an 850px maximum narrative column, a restrained company heading, and an introductory
thesis followed by Business, Industry, Earnings, Valuation, and To watch. White
#ffffff, ink #243347, secondary #68768a, links #285db0, detail surface #f7f9fc;
signed numeric green #089981 and red #f23645. Avenir Next/PingFang carries both
headings and prose. No card grid; one compact disclosure tree explains why Search
is nested within Services. Verification details and metric table are optional opens.

Preserves frozen answers; editorial module reorganizes existing annual research
and checked annual source blocks only. Industry confidence and valuation remain
explicitly limited rather than invented. No quarterly outcomes, new model runs,
adoption actions, or future green/red verification scores introduced.

Browser checked: current-section navigation, readable desktop and 390px mobile
layout without body overflow, and annual segment-profit evidence opens the actual
SEC table with one highlighted source target. Sources remain semantic and period
labelled. Responsive viewport is restored for handoff.

## Annual reliability comparison / 2026-09-16

Follow the same reading palette: white #ffffff, ink #243347, secondary #68768a,
source blue #285db0, separators #e0e6ef. Avenir Next/PingFang, left-aligned narrative
within 52em and a horizontally scrollable results table. The meaningful visual is
the side-by-side actual run comparison; no score cards, decorative animations or
green success banner that could imply research approval. Failed samples stay visible.

Reviewed against the brief: compare failure types and cost, preserve each original
model conclusion, clearly separate citation checks from semantic/numeric review.
Existing companies and research archive were not changed. Added bilingual navigation
and records links, keyboard focus outlines, responsive padding. Browser desktop
screenshot checked: all six completed runs visible, clear costs and pending review.
New derived report views show percentage coverage warnings; frozen raw outputs stay
unchanged. Narrow-screen visual testing remains pending for this comparison page.


## 2026-09-18 · Report editing and revision provenance

Plan: retain the approved reading workspace, with the report in the center and material/version history at right. Use the existing white #ffffff, blue-gray rail #f5f7fa, text #202b3b, muted #596779 and action blue #275dad. Diff removals use #fff1ed and additions #edf5f3, always accompanied by explicit before/after text. Keep Avenir Next / PingFang SC, left-aligned continuous report text with a 76ch measure. The report edit dialog uses a large body field and a short required reason, not a separate generic dashboard. Preserve the companies page.

Review against the research workflow: keep original evidence and historical reports visible; save as a new candidate, never replace adopted content on edit. Agent revision identity belongs to each revision, separate from the researcher stream. Show human/agent, timestamp, reason, before/after text, ancestors and model/run/artifact provenance. Raw JSON was replaced with readable text diffs.

Implementation: Markdown report rendering escapes raw HTML; safe external links only. Existing claim editing remains supported. Human browser requests cannot impersonate agent edits. Local agent revision handoff checks artifact integrity and writes a candidate with provenance. The existing archive rerun entry point now persists its answer as a child revision. No model call starts on human save.

Validation: core archive tests and isolated human → agent revision chains, stale-edit conflict, unchanged source content, source artifact integrity, HTML escaping, and browser API identity controls. Visual browser verification was blocked because the browser tool could not verify its admin-enforced security policy; no workaround was attempted. Full test counts are recorded in the delivery response.

## 2026-09-18 · Site hierarchy and home

Plan: a research desk, with global navigation Home / Companies / Reports. Company overview leads to Materials / Structured data / Research reports; a report leads to its outline, evidence and revision history. Keep raw source views free of application chrome. The home opens on the most recent available report, with an explicit candidate/adopted label and a compact list of ongoing company research. Avoid summary tiles that suggest the 50-company watchlist already has research coverage.

Tokens: white #ffffff, paper rail #f5f7fa, ink #202b3b, muted #596779, blue #275dad, divider #e1e7ef. Retain Avenir Next / PingFang SC and left-aligned reading text. The memorable element is a continuous research path from source material to data to report, backed by actual counts. Layout: global nav; breadcrumb; page title; broad report list with a narrow context column. On narrow screens stack the context column and allow tables to scroll.

Review: the old company page confused source structure with business-semantic data and exposed experiments as top-level product objects. Separate source indexes (inside Materials) from metrics/business map (inside Structured data); group report revisions under one report lineage. Old links remain valid. Company membership and labels do not change. User explicitly requested the company hierarchy, so its navigation is now in scope.


### Scope correction: company-first hierarchy
The user explicitly rejected adding more landing pages. The company list is the homepage (`/` and legacy `/companies`). There is no separate global report dashboard. Enter a company before opening materials, structured data or reports. Alphabet's business map is a child of Alphabet data; document indexes remain children of individual source documents. Existing experimental and legacy URLs remain available for provenance, but are not promoted in product navigation. Other watchlist companies show their actual empty coverage. Previous homepage dashboard proposal is superseded. Changes remain staged, not deployed.

Validation of the company-first revision: 269 tests passed; seven canonical HTML responses and their seven inline JavaScript blocks passed structural/syntax checks. Routes verify company isolation, PDF registry boundaries, document return links, report detail/history, and legacy redirects. Visual verification remains blocked by the previously reported browser policy verification failure. Original running project unchanged.


### Attention dashboard v1 — latest agreed hierarchy
The user now explicitly wants a dashboard homepage separate from the company directory. This supersedes the company-list-as-home decision. Home answers what deserves attention today; company detail prioritizes reading and editing analysis reports. Supporting materials, source indexes and structured metrics remain company-scoped.
Palette: paper #ffffff, rail #f5f7fa, ink #202b3b, muted #596779, action #275dad, review #85531e. Type: Avenir Next / PingFang SC; 32px page heading, 19px sections, 14–15px rows. Left aligned daily attention queue, a compact research-update rail, and subordinate expandable watchlist. Avoid large metric cards: the useful unit is a company plus a specific reason to open its report.
Plan review: no invented market alerts, newcomer counts or real-time dates. Existing priorities seed focus; report timestamps/audit events supply research updates. Missing company-added dates are explicitly unavailable. Local daily checkmarks are labeled as this-browser view state, not archived research approval. Company page gives most space to reports and places sources in a supporting rail.

Dashboard v1 verification: 274 tests pass, including grounded additions, timezone boundaries, exclusion of future updates, priority ordering, version grouping, and local-view checkpoint invalidation. Seven canonical pages and fifteen inline scripts pass response/syntax checks. Browser visual verification remains unavailable: CUA getTab reports the administrator policy cannot be verified. User's affirmative response and revised brief authorize applying this code-only version to the original project; report import remains excluded.


## 2026-09-19 Direct report review workspace

User requested fixed company tabs, left report navigation, direct middle report editing and right source snapshot. Plan: white #ffffff paper, #f1f4f8 rail, #202b3b ink, #566477 secondary text, #275dad selected state; reuse Avenir Next/PingFang SC. Layout: report list 250px | flexible reading/editing | source metadata 280px. All text left aligned. Retain document/researcher scope and revision provenance.

Brief review: remove overview feature cards and separate company report directory; render the existing archive immediately. Move material/report choices to the left, put source identity on the right. Editing is inline and saves through the original revision API. Catalog hashes are explicitly labeled catalog metadata, not falsely described as frozen run inputs. Companies list unchanged. Mobile order is list, report, source. Browser verification and regression results recorded in delivery.

Verification: 54 archive/UI/route tests and 5 report-revision tests passed; extracted JavaScript passed node syntax checking, empty report rendering passed, and git diff whitespace check passed. Restarted local server. Browser getTab was blocked because the admin-enforced security policy could not be verified; no visual/interactive browser pass is claimed. Existing paragraph-90 excerpt integrity gap remains unrelated to this layout change.


## 2026-09-19 Sidebar simplification

User explicitly prefers Claude/Anthropic styling. Reference: https://www.anthropic.com/ (text reference accessed; no claim of screenshot matching). Plan: warm paper #f5f4ef, reading #faf9f6, rail #eeede7, ink #30302b, muted #77766d, terracotta #a65d43. Use Avenir/PingFang for controls and Georgia/Songti for report headings. This intentionally follows the requested visual direction. Left rail contains only a researcher selector and one title per research material; scope, status filters and all historical versions remain accessible in collapsed right-side settings. Review against brief: hierarchy reduction is the main change, with quiet typography supporting reading. No company list or research data changes.


## Stable inline editing and fixed operations

User rejects layout replacement and scrolling to find actions. Reuse warm palette and existing typography. Keep the rendered document in place; editable text nodes preserve heading, paragraph, table and citation structure. Map Markdown blocks/cells back to source lines, leaving unchanged lines byte-for-byte intact. Plain-text paste and single-line block editing avoid browser-created structure changes. Save/cancel/revision note share a sticky toolbar; secondary actions remain in More. Existing revision API retains provenance and conflict guards. This pass edits text within existing blocks, not document structure. No visual verification is claimed while browser policy verification remains unavailable.

Validation: 54 archive/UI/route regressions and 5 revision tests passed. Heading/list/table source mapping and bold rendering checked; JavaScript syntax check passed. Browser interaction remains unverified under the existing policy restriction.

## Paragraph highlights and revision locations

User requested soft whole-block hover/focus instead of a left rule. Apply #eeeae2 without padding or font changes so editing does not shift layout. Revision history now projects persisted before/after values into individual changes, labeled by claim paragraph or Markdown source line, and displays save time. Preserve human/agent attribution and revision lineage; record on confirmed save, not each keystroke. Existing 54 archive tests and 5 revision tests passed; checked paragraph location, unchanged-block omission, additions and HTML escaping. Browser visual verification remains unavailable.


## Block review lifecycle

Hover highlights a text block; double-click (keyboard Enter) edits that block directly. A nearby acceptance control persists the block hash, actor and timestamp under the snapshot transaction/revision guard. Toolbar shows content acceptance count. Content approval is distinct from validated report-baseline adoption. Human/agent revision inheritance retains only unchanged block hashes; claims include citations in the hash. Markdown table cells are review units; headings and text lines correspond to rendered blocks. No automatic approval or model call. Browser visual verification remains blocked by the existing policy check.

Validation: 54 archive/UI/route tests plus 9 block-review/revision tests passed. New cases cover persisted acceptance, undo, stale revision rejection, changed-block invalidation with unchanged approvals retained, citation-sensitive hashes and table cell mapping. Extracted JavaScript syntax and whitespace checks passed. Whole-report baseline adoption moved into More so the primary workflow is block review.


## Lower-right acceptance and review sidebar tabs

User requests an unobtrusive lower-right acceptance control with a brief dismissal delay. Anchor below each claim (including citations) or rendered report text block; reserve whitespace, retain for 800ms after pointer exit, cancel dismissal while hovered/focused, hide on scroll. Do not move upward over text when viewport space is insufficient. Right rail now has accessible Sources, Revisions and Cross-review tabs. Cross-review is a clearly marked future execution entry: no fabricated results or model invocation. Proposed unit is a frozen whole report with paragraph-level findings and model/evidence provenance. Existing visual verification restriction remains.


## Text-local feedback

Anchor the compact acceptance/like/dislike control near the pointer over the actual text, not the containing claim/citations card. Dislike opens an inline reason form and freezes the target while entering text. Persist feedback through the existing opinion pipeline with source answer, block hash, researcher, vote and timestamp; mark carry_forward for the existing reanalysis context. Preferences are pending feedback, not automatically adopted general rules. User's negative assessment of Team's first paragraph is recorded in the task feedback below without guessing which historical version or detailed reason was intended. No new model run.


## Stable paragraph footer, replacing pointer-following controls

User screenshot shows cursor-adjacent controls obscuring prose. Remove pointer coordinates, fixed positioning and mousemove listeners. Reserve a 36px footer immediately after each text block, before claim citations; align controls right. Table cells share a footer after the table to preserve valid markup. Hover changes opacity over 140ms with no translation; dismiss after 600ms, retain during focus/feedback. Feedback form expands in document flow, never overlays prose. Editing hides controls but retains the footer space. Reduced-motion disables fades. Visual verification remains unavailable; screenshot diagnosis is user-provided.


## Insert and delete content blocks

User requests hover plus between paragraphs, typed insertion and persistent top-right deletion; dragging deferred. Insert facts, inferences, hypotheses or questions in-place as an unsaved draft. Save/cancel uses the fixed toolbar. Server derives structural changes from the persisted answer and validated indices; existing citations are preserved, inserted claims have no fabricated citations. Deletion removes a block from the new revision only. Unchanged unique content hashes carry acceptance across shifted positions. Table deletion is whole-table. New content remains unverified; no automatic fact approval. Visual verification remains unavailable.

Validation: 54 archive/UI/route checks and 14 structure/feedback/acceptance/revision checks passed. New cases cover insertion without citation mutation, acceptance migration across shifted indices, original-version retention after deletion, invalid positions/types/empty content, stale versions and Markdown table removal. JavaScript syntax and whitespace checks passed. Structural editing handles one insertion or deletion per confirmed save; cancel restores the draft.


## Selection endpoint polish

Shortened block acceptance label to 采纳 / Accept. Annotation feedback toolbar anchors above the selection focus endpoint, with backward/multiline fallback and viewport clamping; no change to annotation content. Deferred editorial bold/keyword emphasis to future report authoring as requested. JavaScript syntax and 26 annotation tests passed; browser visual verification remains unavailable.


## 2026-09-19: production home card workspace

User-approved direction supersedes pagination and expanding the whole layout. The real home now uses fixed card boundaries: reading queue, company research changes/recent/history, new companies/watchlist, and explicit disconnected news/portfolio states. Hover reveals a short excerpt inside the item; click reads inside the same card. No popup, backdrop or neighboring card reflow. Local read marks bind to report revision, not daily company checkboxes, and do not approve research. Full report links preserve the established evidence/edit workflow.

Palette: paper #F3F1EC, card #FCFBF8, ink #302F2A, muted #716D64, line #DFDBD2, accent #96503B. Songti headings with system fallback; compact sans-serif body. Main card occupies two rows; remaining modules use smaller cards. Native local scrolling; mobile uses horizontal card browsing. Shared navigation is sticky with restrained compact typography on scroll, reserving its height to prevent jumps. All text bilingual. Unknown company additions remain unknown; historical records exclude future/deleted records.

Source render and focused tests required; browser visual verification unavailable under current browser policy, so actual viewport/trackpad review remains manual. No model calls, financial data generation or deployment involved.


## Company directory compact pass

User explicitly requested company directory optimization. Remove duplicate product header, oversized hero and four KPI blocks. Compact heading, existing search/index/attention/holding filters, horizontally scrollable theme filters, then one continuously scrollable company table. No pagination; all 50 recorded companies remain filterable. Sticky table headings and shared navigation stay visible. Redundant sector/tag display is removed from rows; tags remain searchable. Selection policy and dated source links remain under Scope and sources. No company data, holding labels or research decisions modified. Palette follows shared paper/ink/line/accent tokens; 23px Songti heading, 13px company titles, 11–12px metadata. Code and rendering checks performed; browser visual review remains manual under current policy.


### Reference calibration

Read the local uteki research-exoskeleton mock styles and production company workspace, viewed its saved 2026-05-31 harness desktop screenshot, and read rain.blog global/article styles. These are references, not user-confirmed favorite screens. Preserve this app’s single-window table workflow; borrow restrained surfaces, stronger company names, neutral secondary text and cohesive controls. Avoid copying the screenshot’s large hero or sidebar, which conflict with the current request. Corrected a bilingual heading span selector that shrank the title. Applied a page-scoped six-color palette and compact segmented controls. Current page has not been visually verified in-browser; do not equate unit tests to design approval.


## Versioned style baseline

The maintained interface baseline is [Uteki interface style guide](../skills/uteki-interface/references/style-guide.md), loaded by [the reusable skill](../skills/uteki-interface/SKILL.md) and repository AGENTS.md. Historical notes above are implementation history; the maintained guide and latest user requests govern future decisions.

Home hover now reserves two lines for the excerpt, avoiding height changes and row displacement. Mouse focus does not leave a focus ring; keyboard focus remains visible. Only a subtle background/opacity change remains. This is not final visual approval.


## System-wide interface consolidation

The shared style guide now has an implementation token file: `apps/review_workbench/design_tokens.css`. Theme injection loads it before component styles. Company/research/home color forks are removed or mapped to shared tokens; retired homepage renderer and early company universe styling removed. Company detail headings, report rails/body spacing, source/data tables and shared controls are consolidated. All original snapshot, citation, review and edit behavior is retained. See [interface review matrix](INTERFACE_REVIEW.md). Browser visual review is still pending under current access policy; automated tests do not constitute visual approval.


## Company brief: judgments before metadata

Company overview now renders the selected recorded report’s actual judgments immediately, preserving original wording and status. Compact company heading; author, revision, report date and source identity in the right context rail. Subsequent judgments expand with a 200ms height transition within the reading region; reduced motion switches immediately. Archive is disclosure-only; full report and evidence links remain. Explicitly not a newly generated recent-performance brief. Dedicated company_brief CSS/JS avoids changing other workspaces. Browser visual review pending.


## 2026-09-20 批阅交互收尾

沿用正文、段落操作条和修订历史；操作为采纳／拒绝／编辑。淡绿 #e8f4eb 表示采纳，淡红 #fbe9e7 表示拒绝，保留文字按钮及按下状态。两种决定均计入已批阅（n/N），全部处理后为已完成批阅。旧撤销记录不算拒绝。编辑复用新候选和差异记录，变更块的决定失效。引用点击只展示记录中的摘录，可点外部、关闭按钮或 Escape 关闭，不加载整篇文档；保留主动打开来源入口。浏览器策略校验不可用，实际视觉验收待用户反馈。
