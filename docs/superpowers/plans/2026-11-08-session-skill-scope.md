# Session Skill Scope Implementation Plan

> Execute inline in the existing investigation-skills candidate. Preserve unrelated state edits. No CI authorization.

**Goal:** persist optional session methods while freezing each instruction and retaining instruction-owned skill activity.

**Architecture:** add revisioned method preferences to the existing Thread ledger and command protocol. Freeze admitted identities at input acceptance. Native execution receives optional method guidance; actual loading and reporting retain existing activity records.

**Tech Stack:** Python, PostgreSQL, React, TypeScript, existing Pi runtime.

## Constraints

No fixed first action, keyword routing, new ledger, extra model pass, implicit business-context inheritance or expanded grants.
Only native method roles may be session preferences; professional binding remains explicit application admission.
In-flight work keeps its snapshot. New sessions start empty. All source and evidence rules remain in force.

## IG1 steps

- [x] Add `session_skill_preferences.py` and tests for revisions, duplicate/private fields, exact skill versions and local exclusions.
- [x] Extend `thread_protocol.py`, `thread_work.py`, `thread_input.py` and `thread_service.py`: snapshot, dedicated command, JSONB column, idempotency, atomic revision and instruction freeze.
- [x] Extend `delegated_runtime.py`: optional frozen method guidance without changing plain input to skill invocation.
- [x] Extend App snapshot parsing and event recovery; add `SessionSkillSettings.tsx` beside existing session controls. Keep the single composer and its per-instruction skill control.
- [x] Add current-instruction exclusions to `threadInput.ts` and `ThreadCommandMenu.tsx`; accepted drafts reset these through the existing draft boundary.
- [ ] Verify malformed exclusions and stale catalog behavior across the actual input contract; test frontend invalid saved drafts.
- [ ] Verify PostgreSQL restoration, concurrent revisions, fresh-session isolation and real two-instruction skill records.
- [ ] Run canonical rebuild; check readiness, role source/image identity, saved products and refresh in an existing browser tab.
- [ ] Review changed code; commit only task-owned files. Record limits, source identity and control state. CI/dev merge require separate approval.

## Focused commands

```sh
uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_session_skill_preferences.py packages/capstone-agent/tests/test_thread_input.py packages/capstone-agent/tests/test_thread_work.py packages/capstone-agent/tests/test_delegated_runtime.py -q
npm --prefix packages/capstone-app test -- src/SessionSkills.test.tsx src/sessionSkills.test.ts src/threadInput.test.ts src/threadProtocol.test.ts src/threadWorkProtocol.test.ts src/threadProjectionStore.test.ts
npm --prefix packages/capstone-app run check
make doctor
git diff --check
```

A missing test database is a skipped persistence check, not a pass. Browser connection is currently unavailable; component checks do not grant visual acceptance.

## Successor

IG2 adds optional editable start examples to the existing empty state. IG3 adds evidence-bound next actions. IG4 adds investigation continuity and scope-change recovery. These remain separate acceptance units in the canonical unified-execution worklist.
