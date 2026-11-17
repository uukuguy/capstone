# Compatible session restoration

Owner capstone-app. Branch fix/compatible-session-restoration-20261117 targets dev
from58782e03. User requires compatibility while new and old records coexist.
New-session entry already creates v2 enterprise research Threads and uses
send_message. Protocol v2 also holds task-style Works without conversation_mode;
these are not empty Threads and must not be silently migrated or deleted.
Task-style Work remains a supported Control delegation mechanism. Retire obsolete
entrypoints and callers, not shared Work execution based only on conversation_mode.

Evidence: newest15 inspected Threads all contain saved task-style Works. A real
completed sample shows welcome content until its historical Work is selected;
then its original instruction appears. Preserve the existing read-only history
and admitted attempt/product ownership rather than merging unrelated records.

1. Add failing default-restore regression. Cover new conversation, legacy-only,
   mixed Works, valid saved selection, new draft/explicit new intent and pending
   commands. Preserve protocol1/professional entry behavior and all stored data.
2. Resolve an initial missing/blank selection after local state is loaded:
   existing valid selection first, then conversation Work, then latest task Work.
   Preserve new drafts and explicit new selection. Choosing history never sends
   a command, creates an Attempt or changes the backend representation.
3. Run focused App consumers/types and read real historical examples through
   the rebuilt candidate. Verify no model execution and no data/pin changes.
   Integrate focused macOS dev PR, rebuild actual5173 and verify again.
4. Record the accepted future lifecycle: inventory important old records,
   explicit conversion with lineage/products/evidence preserved, replay checks,
   retire old writes, then remove compatibility only when remaining old readers
   are accounted for. This is backlog scope, not migration during this fix.
5. Update canonical worklist/register/graph and exact deployed source before
   final control-only closeout. Final own CI/merge/HEAD receipts remain ignored.
