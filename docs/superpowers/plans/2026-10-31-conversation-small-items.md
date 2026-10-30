# Conversation repair plan

User approved the repair scope on 2026-10-31. Delete confirmation placement and
keyboard behavior passed user manual acceptance and need no further test.

Keep existing conversation components, authoritative event ownership, saved
drafts and exact uncertain-command retries. Never infer actual cancellation
from a local button click.

- [x] Add a submitted instruction before its optimistic Thinking record; replace
  both with admitted events. Test delayed acceptance and failed submission.
- [x] Connect Escape to the same cancellation path as Stop, without overriding
  dialogs or menus. Test disabled state and repeated input.
- [x] Use consistent revision-conflict copy: rejected request did not execute,
  input remains, synchronize before retry. Test rejection feedback.
- [x] Extract bounded human-readable messages from JSON tool failures while
  retaining raw diagnostics. Test nested and malformed values.
- [ ] Run affected App tests and type checks; rebuild local runtime, inspect the
  real App, and record evidence. Integrate through a focused dev PR.

Files: CapstoneAssistantThread.tsx, ThreadWorkAdapter.tsx, threadFeedback.ts,
their focused tests, and project control state. No authority or gateway changes.
