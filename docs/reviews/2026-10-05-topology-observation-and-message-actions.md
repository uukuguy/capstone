# Topology observation and message action repair

## Cause and change

Read-only inspection of the reported local Thread found two topology
instructions ending with `capability_required`. The latest Attempt had 13
successful context, component and dataset calls. Its selected model and
authority revision were correct. Admission ran before diagram projection and
rejected the answer because the Domain Pack observation allowlist omitted
`topology.components.get`.

The fix adds that published read-only, no-evidence capability and the two
published operation catalog calls to the existing observation policy. It stays
in the Domain Pack. No model-specific instruction, result, count or topology
was added to production code. Failed tools and endpoint/AC calls without
required lineage still cannot use the observation path.

Desktop message actions retain hover/focus visibility. User actions no longer
increase bubble height; assistant actions use the existing duration row instead
of reserving a separate empty row. Short answers use a bounded column width to
keep controls inside the viewport. Touch layouts retain visible 44px controls.
The unfinished feedback actions move into More as disabled items. More closes
on Escape, focus departure or outside click, and opens downward when the upper
scroll boundary would clip it. An open menu stays fully opaque.

Common answer actions retain seven fixed slots: copy, grid view, result,
evidence, process, retry and More. Missing content disables its control instead
of removing it. Expanded/selected controls use a pale green background and
green icon without borders or badges. At narrow desktop widths, hover/focus
replaces duration text in the same row; it adds no empty row or height change.

Completed answers can repeat their original instruction as a new Turn/Attempt.
Failed, cancelled or interrupted answers keep the original retry endpoint.
Completed reruns require normal send eligibility, an original instruction,
the same model Context and no pending model/profile change. These checks keep
an old answer from rerunning against a different active model. The backend's
committed-Turn restriction remains unchanged.

Model-directory activation now sends only the model-open instruction. The
authority-backed diagram still follows the selected model through the existing
projection. The root App opens the live conversation entry; `/old` and `/old/`
serve the original registered cases. New Threads write their IDs into the URL
so refresh resumes them. Existing query links and the private/public credential
separation remain intact. Both READMEs and the runbook reflect these routes.

GBnetwork failed a separate 2,000-bus projection limit despite opening correctly.
The authority now builds and validates complete operator geometry under one
10,000-bus, 20,000-branch, 4 MiB contract. Its catalogue preflight uses the same
geometry and UTF-8 encoding. Unsupported models carry a safe reason, are disabled
in the directory, and are rejected by server-side creation and switching.
Catalogue eligibility is cached before the model revision becomes visible.
The protected simulator subtree remains protected with its reviewed baseline.

Diagram-only subprocess, worker, ledger, HTTP and browser bounds now agree.
Ordinary ledger events retain their 64 KiB bound. PostgreSQL selects byte-bounded
event pages before decoding payloads. SSE checks each UTF-8 frame, including
coalesced chunks. The browser shares immutable diagrams as each restoration page
arrives; a stale load cannot publish its private cache. Large graphs without
coordinates use graph levels instead of an all-pairs force layout. Authority
coordinates remain unchanged.

Command rejection, Attempt failure and projection failure show a concrete reason,
a recovery action and a safe diagnostic code. Projection failure still preserves
a committed answer. No raw exception or private path enters this feedback.
The directory uses 9px popup text and an 8px hint with a restrained focus border.
Keyboard browsing requires Enter; reopening after Escape resets the tentative
choice so clicking the same candidate can open it. Draft text remains intact.

## Verification

- Policy regression failed before the fix: four failures included topology
  components and both operation catalogs. All 23 policy tests passed after it.
  Contract coverage checks every published, non-mutating, no-evidence model
  or catalog capability; negative tests preserve lineage requirements.
- The real-authority Thread regression reproduced `capability_required` for
  the reported model before the fix. Five registered models then passed two
  consecutive topology instructions each: the reported model, RTS, IEEE-39,
  GBnetwork and case9241pegase.
  Completed answers have no analysis result/evidence refs, and diagrams bind
  to the same selected model, revision and Context.
- The More test failed while feedback buttons were exposed. Final App tests
  passed: 245 tests in 21 files. Fixed-slot, completed-rerun and route tests also
  failed before their changes. TypeScript/Vite build passed with its existing
  large-chunk warning. Independent review passed policy and focused App suites,
  then approved the final rerun guards, routing and large-diagram changes.
  Follow-up review closed SQL page sizing, UTF-8 size consistency, cache
  publication, native selection and per-page geometry sharing. No findings remain.
- `make test`, `make test-e2e`, `make validate` and `make doctor` passed. E2E
  covered 39 cases and three registered-worker checks. The executable static
  analysis matrix remains 24/24. Final App checks follow the later UI changes.
- Local playwright-cli reproduced the two exact user instructions with finite
  Pi decisions and real gridctl facts. Both completed with the selected model's
  10-bus/9-branch diagram. Refresh and old/latest answer graph selection passed.
- Desktop hidden/hover/focus states have equal message heights. The seven-slot
  bar initially overlapped duration text at 821px; the final shared-row swap
  fixed this without changing height. More bounds passed at 821, 1040 and
  1440px; Escape and Tab departure close it.
  Phone 390px checks passed disabled feedback, outside dismissal, 44px actions
  and no horizontal overflow. Screenshots were inspected.
- The model directory sent exactly `打开 case57 电网模型`. Real gridctl returned
  its 57-bus diagram. Clicking its completed-answer retry produced a second
  completed answer and retained the first; refresh kept both. Toggle on/off
  colors and selected-grid state passed in the browser. The root opened the
  Thread entry, and the real local `/old` page opened the registered-case UI
  without submitting a case. StrictMode creation/reload tests confirm one
  initial Thread request and no extra creation on reload.
- Final checked-in local rebuild, readiness, App HTTP 200 and matching API/
  worker image checks passed. The read-only runtime receipt records the exact
  image and current user Thread; its history was not changed.
- Real browser GBnetwork renders all 2,224 buses and 3,207 branches; zoom and
  refresh passed. case9241pegase renders all 9,241 buses and 16,049 branches,
  and refresh retains the full diagram. Both screenshots were inspected.
  Keyboard browse, Escape, reopen and same-candidate activation passed with
  the Composer draft retained. Each open sends only the model-open instruction.
- Authority model/protocol checks passed 33 tests. A real PostgreSQL fixture
  restored three diagrams across three byte-bounded pages, preserved the
  ordinary-event limit and claimed no user Attempt. Full `make test` passed,
  including 925 grid-agent, 178 simulator, 465 Capstone Agent and 245 App tests.
  The host gate skips optional PostgreSQL cases; the separate fixture covers
  the changed real-ledger path.
- `make check-types` passed with zero errors after explicit integer validation
  at the authority contract boundary. The focused 33 authority checks passed
  again, and independent review approved this final correction.
- Documentation links, relative CLAUDE symlink and diff checks passed.

Receipts: ignored `runs/topology-open-repair/`. Screenshots: ignored
`output/playwright/topology-open-repair-*.png` and `stable-actions-*.png`.
The isolated browser assembly
omits the legacy Case preview endpoint and has two known 404 console errors.
Finite sessions verify the contract and authority path, not arbitrary Provider
planning. No Provider or cloud call occurred. Test-only services, browser and
temporary auth were removed; normal local API/App remain running.

An existing failed Attempt remains immutable. Refresh and resubmit its
instruction to run it with the repaired backend.
