# CONV-04: Pi reference mode and context isolation

Status: proposed implementation contract; awaiting user review.

## Purpose and accepted constraints

Provide a pure Pi comparison path in the existing Thread. Preserve the gateway,
streaming, cancellation, persistence, reconnect and replay. Reference output is
unverified text. It cannot supply business facts, results or evidence.

This refines the accepted runtime and isolation decisions in the
[interaction record](2026-09-29-agent-interaction-discussion.md#runtime-paths-and-comparison).
Delivery belongs to CONV-04 in the
[canonical worklist](../plans/2026-10-07-capstone-conversation-completion.md).
It is separate from the locally verified ordinary Capstone conversation.

## Implementation evidence

- `harness.py` already has `HarnessPiClient` and mode-tagged runtime events.
  Its mode is a factory setting, not a persisted per-Attempt decision.
- `thread_protocol.py` Attempt snapshots contain identity, phase and target
  Context; they have no runtime or authority mode.
- `thread_service.py` stores and claims Attempts in memory and PostgreSQL.
  Previous instruction selection filters by ModelContext, without mode isolation.
- `thread_application.py` prepares a business application before creating its
  Pi client. The empty-selection ordinary path still supplies application policy
  and model context; it is not a pure Pi baseline.

## Options and recommendation

| Option | Benefit | Cost |
| --- | --- | --- |
| Mode switch in the existing Thread, with immutable Attempt modes | Matches accepted history, controls and isolation decisions | Requires durable mode state and mode-scoped memory |
| Separate reference Thread | Simple history separation | Does not provide the accepted in-Thread switch and restoration |
| Reuse ordinary Capstone with tools disabled | Small runtime change | Retains business policy and context, so it is not a pure baseline |

Recommend the first option. Keep the existing Run and ModelContext identities.
The gateway owns mode state; a Domain Pack does not own reference mode.

## Public control and persistence

Add a bounded `switch_runtime` command accepting only `capstone` and
`pi_reference`. Reject `dsh_reference` as unavailable. Retain existing command
authentication, idempotency and receipt rules.

Expose `runtime_mode` on the Thread snapshot and immutable `runtime_mode` and
`authority_mode` on each Attempt. Use `authority_mode=capstone_admission` for
Capstone and `authority_mode=none` for Pi reference. The former identifies the
admission path, not a promise that an answer contains authority facts.
An ordinary Capstone answer may still have no results or evidence.

Apply a switch only when no Attempt is active or queued and no Case owns the
Thread. Otherwise return a clear conflict and leave state unchanged. This
avoids an additional pending-switch queue in this work package. Record the old
and new modes in a public `runtime_mode_changed` control event.

Retry captures the original Turn's mode, even if the current Thread mode has
changed. The retry must not replace the Thread's selected mode. Events retain
the Attempt's mode throughout execution and replay.

Store Thread mode durably and Attempt modes with the existing immutable Attempt
record in both ledger implementations. Read legacy records as Capstone mode;
validate new fields strictly. Update Python and App readers together. Preserve
the existing bounded snapshot/event envelopes and schema compatibility checks.

## Reference preparation and memory

Dispatch on the claimed Attempt mode before business application preparation.
Pi reference uses the managed Pi launcher, protected Provider configuration and
the same gateway event sink. Do not provision Authority access or Domain Packs.
Disable built-in tools, extensions, skills and workspace instruction discovery.
Do not inject Capstone policy, business tool descriptions, registered model
metadata, application catalog, prior result handles or business dialogue.

Supply the user's current text and bounded prior Pi-reference reader text only.
Use the existing text bounds. A fresh reference session must not inherit the
business Pi session. Capstone memory selectors admit only Capstone Attempts;
reference selectors admit only reference Attempts. Apply the same rule in
memory and PostgreSQL. Mode is an explicit selector, not inferred from answer
text or tool availability.

Keep active model, capability selection, model workspace and saved model views
unchanged. Disable model, selection and scripted-Case mutations while reference
mode is selected, with a short instruction to return to Capstone. This preserves
the exact business state without adding a second model-state owner.

Users may paste reference text into a later Capstone instruction. Treat it as
user-supplied unverified text. Do not add automatic reference-message import or
promote its content into evidence.

## Output and failure handling

Reference answers use an explicit `Pi reference · unverified` marker in live
history and replay. Emit runtime and authority modes on Attempt events. Reference
completion always has empty result/evidence references. Reject tool activity,
result projections or evidence admission from the reference path before commit;
a display label alone is not sufficient protection.

Use existing cancel, interruption, lease recovery and duplicate-command rules.
Reference failure remains a Turn failure; it does not close the Run. Historical
business results remain available in their own history, but cannot appear as
references supporting a reference answer.

## App behavior

Place a small runtime selector in existing conversation settings. Default to
Capstone. Explain Pi reference with one sentence: no business tools or verified
calculation results. Disable switching during active or queued work and Case
execution. Preserve composer draft, focus, history folding and model view.

Show mode markers from persisted events, rather than the current selector.
Reconnect restores the selected mode from the snapshot. A reference reply stays
marked when the user returns to Capstone or reopens the Thread.

## Verification and delivery

1. Protocol and command checks: strict fields, old-record defaults, busy/Case
   rejection, idempotency, retry mode and immutable Attempt mode.
2. Both ledger implementations: reconnect, replay, mode-specific previous text,
   unchanged business model/selection and atomic mode switching.
3. Runtime checks: no domain provisioning, business context or tools in reference
   Provider requests; forged tools/results/evidence rejected; cancellation works.
4. App checks: selector state, disabled controls, persistent answer markers,
   mode restoration, retained draft/focus/model and keyboard/mobile use.
5. Loopback Provider with real managed Pi RPC: business → reference → business,
   isolated request contexts, empty reference handles and unchanged model state.
6. Run scope-appropriate integration gates and local rebuild; verify API/worker
   identity and the actual App entry point. Record a local receipt.

Real Provider billing and remote deployment need their separate authorization.
Do not claim cloud acceptance from local tests.

## Exclusions

No DSH implementation, capability-parity reference profile, native-runtime tool
integration (CONV-05), multi-Run branches, automatic reference import, public
shell access, Provider switching or independent Thread API.
