# Model Reference and Cross-Family Thread Audit

Date: 2026-10-03

## Scope

This audit follows the complete user path from the federated model catalog to
model selection, context activation, family worker leasing, and the Web/TUI
conversation entry points. It covers the failure where `model_energy` was
reported as unavailable while the registered PyPSA model was
`pypsa-example/model_energy`.

## Rules now enforced

- The application catalog is federated and contains metadata from both
  pandapower and PyPSA. A family worker may explain all registered models, but
  it may execute Attempts only for its own implementation family.
- User-facing model references resolve in this order: canonical model ID,
  case-insensitive canonical ID, unique final path segment, then unique
  display name. Ambiguous references are rejected with the candidate IDs;
  the client never guesses.
- Short control phrases such as `打开 model_energy` and `切换到 IEEE-39` are
  translated to the explicit `switch_model` protocol command. The canonical
  command still carries the full registered model ID.
- `打开 IEEE-39 网络并解析线路 11 的端点。` and other longer requests remain
  ordinary agent work; they are not intercepted as a model switch.
- The short-control heuristic is language independent: unknown short Chinese
  references are reported as unknown, while longer English or Chinese
  analytical phrases remain normal agent requests.
- Selecting the already active model does not create a second context. A
  fresh context requires the explicit `重新打开 ...` / `reopen_model_context`
  path and a recorded reason.
- Web and TUI use equivalent reference matching and same-model behavior. The
  server contract remains explicit and typed; neither client receives
  Authority internals or raw model objects.
- TUI carries the catalog's bounded worker-availability state and reports an
  unavailable family before submitting a command, matching Web behavior.
- A diagram is shown only when its model ID and revision match the active
  context. A family switch therefore cannot leave a stale pandapower diagram
  visible for a PyPSA context. Generic PyPSA diagram projection remains a
  follow-up surface for M9.

## Verification

- Web catalog and Thread interaction tests: 19 focused tests passed; full App
  suite: 164 tests passed.
- TUI model command and Thread command/Attempt tests: 12 focused TUI tests
  passed; the broader focused Thread set passed as well.
- App TypeScript check and production build passed.
- The existing M8 federated catalog and worker-boundary tests remain covered;
  no compatibility entry point was changed to bypass `capstone-agent`.

## Follow-up boundary

The current fix deliberately keeps model control as an explicit Thread
command. Natural-language interpretation remains the agent's responsibility
for longer analytical requests. M9 should add a generic, revision-bound model
diagram projection for PyPSA rather than reusing the pandapower preview.

## Independent review disposition

The independent review found no high-severity defect. It identified two
medium UX risks: a language-sensitive unknown-reference heuristic and missing
TUI availability metadata. Both were corrected in this audit and covered by
the added Web/TUI tests. It also confirmed that rejected receipts are now
shown with their status and reason rather than a false success notice.
