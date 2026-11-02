# Session gateway binding

Accepted by the user on 2026-10-31. A conversation has one gateway instance.
Only a conversation with no submitted instruction can change its selection.
An input draft does not count as a submission.

The App shows the current conversation's instance and lock state in the left
sidebar. An empty conversation can select a registered connection. After its
first accepted instruction, the switch button is disabled and explains that
another instance needs a new conversation. The backend enforces the same rule.

The application stores the connection reference, instance ID, public display
identity, and lock state in the Thread ledger. First instruction admission and
locking use the same transaction/row lock. Rejected instructions do not lock an
empty conversation. Concurrent selection and admission cannot mix identities.
Older conversations recover their identity from their first saved attempt;
their history is not rewritten and an unknown historical source is not replaced
by the current default.

Each future instruction refreshes only the bound instance's publication. Same
instance contract updates are allowed. Each accepted execution carries its own
catalog revision. Runtime routing, nested calls, receipts, model displays, and
resource metadata use that source. An address with a replacement instance ID
is rejected. Unavailability never causes automatic fallback to another instance.
No credential is stored in the conversation or sent to the App.

Implementation sequence:

1. Add durable binding/admission, protected source lookup, and session endpoints.
2. Bind sidebar state, switch permission, and source display transport to the
   current conversation. Reuse existing controls and public projections.
3. Run focused local checks, including real PostgreSQL restart/concurrency checks.
   Rebuild through the canonical local entry point and verify in the existing
   browser tab. Do not start CI, push, or change cloud environments.

Gateway business tool names remain dynamically published. The fixed display
operations are existing Capstone App contracts, not gateway business routes.
