# Mission conversation delivery

Owner: capstone-control, capstone-agent application adapters and capstone-app.
Destination: dev. Branch feat/mission-foundation-20261118 depends on accepted
intervention baseline dev38a9e77f. User authorized continuous delivery through
rough-intent creation, progressive planning and dynamic task equipment.

## Accepted outcome

The existing composer accepts `/mission` plus a rough objective. Creation persists
planning state and a verified origin Thread before sending a normal planning turn.
No task form, mode icon or modal is required. `/goal` remains one Agent's objective;
Mission Control organizes Goals and overall delivery. An Agent may later delegate
internally without changing responsibility for its Goal.

The same Control aggregate backs old Goal and new Mission projections. mission_id
aliases goal_id; existing records, events, task bindings and products are not copied.
Planning may have zero Tasks and incomplete acceptance criteria. It is not delivery.
Executable Tasks require objective, delivery conditions, bounded execution and admitted
equipment. Incremental plan updates preserve unrelated active Tasks and their history.

## Implementation and acceptance boundary

- Versioned Mission create/read/command contracts and same-store identity, with
  idempotency, revisions, workspace ownership and explicit planning readiness.
- Verified Thread origin association survives lost create/attachment receipts.
  One nonterminal Mission per originating Thread until an explicit durable selection
  mechanism exists. Ordinary follow-up addresses that Mission, not an arbitrary ID.
- Registered application tools read and update the bound Mission, prepare Tasks,
  admit readiness and request pause/resume/cancel. Execution authority and parent
  worker lease bind all calls. Models cannot claim acceptance or simulator evidence.
- Task equipment resolves registered capability/profile IDs and exact revisions,
  narrows actual child runtime tools and survives discovery. No selection grants
  access beyond the origin's admitted capabilities. Origin gateway selection must
  carry through an application-owned registered binding, never host credentials.
- Defaults allow immediate planning without configuration. Models can recommend
  task-relevant equipment and explain choices in normal dialogue. Active task grants
  cannot silently change; pause confirmation precedes replanning executable grants.
- Shared Goal readers recognize explicit Mission metadata and empty planning state;
  ordinary legacy Goal validation remains strict. No planning Mission may hide old
  Goals or break their pagination and recovery.
- A persisted task-boundary review intent resumes the originating organizer through
  a typed internal command. It never fabricates a user message. Reviews are bounded,
  coalesced while busy and keyed by admitted source state; unchanged state cannot
  repeatedly consume model calls. Paused/cancelled/stopping work does not auto-resume.
- Verifying all currently known Tasks requests organizer review. Mission delivery
  additionally requires explicit conclusion at the current plan revision, nonempty
  verified results and no active execution. This preserves progressive planning.
- Saving a Task product and checking its hash proves persistence, not satisfaction
  of the user's objective. Conclusion records a verdict for each current criterion,
  with exact admitted saved-result references. Only all-met verdicts may deliver;
  unmet or unknown criteria retain partial findings and wait for user direction.
- An immutable source has the same resource identity in organizer and child grants.
  Destination Thread/Work ownership still governs every read. Older frozen grant
  identities remain valid only under their original exact grants. No text alias
  substitution or user-data migration is required.
- Necessary registered resource-read protocol helpers remain available only when
  the frozen Task has admitted inputs. Explicit denials still take precedence;
  this does not restore the whole tool catalog or widen source access.

Current equipment adapter supports registered tools and native resource profiles.
Skill and versioned business-resource equipment adapters are requirements retained
for later implementation; unsupported references fail readiness. Existing authorized
conversation material/resource mechanisms remain available under their own contracts.
Tool denial alone does not establish a semantic read-only guarantee if an admitted
shell tool can still write. The exact tool subset, not a label, is enforced.

## Real acceptance

Start from a rough `/mission` in the existing conversation and show planning with
no full task list. Clarify direction in a later turn; observe model-issued, persisted
plan changes and registered equipment selection. Admit a bounded real Task, inspect
its exact frozen tool subset and saved product, then continue from the same mainline.
Exercise pause/replanning, refresh and uncertain creation recovery. Inspect mixed old
Goal/new Mission boards and original source links. Keep deployed, verified and merged
states separate; unit tests are not a replacement for this model/tool/product path.

Focused tests cover memory/PostgreSQL origin races, legacy compatibility, grant and
registry revision checks, model bridge owner/lease/source checks, SDK discovery bounds,
App request identity recovery and composer interaction. Run canonical local rebuild
before browser acceptance. Use only scoped macOS CI for development integration.

Published model equipment schemas list only implemented adapters. Frozen input
resources are carried through dependency grants, not guessed equipment references.
Model plan changes must pass exact registry preflight before they are stored.
Conflict repair hints cover both current revisions and exact saved-result references,
without returning raw exceptions or adding model calls.
