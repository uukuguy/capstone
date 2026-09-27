# Provider-backed demo answers and safe automatic-stop controls

## Goal

The public workbench must use a real LLM to turn current-run `gridctl` facts
into the reader-facing answer. The same committed answer text must appear in
the timeline and the report. The automatic execution control must only allow a
stop at a safe pause point.

## Design

### Provider-backed public sessions

- The App creates the registered pandapower/PyPSA case in `provider` mode with
  the server-selected provider and model; it does not send credentials.
- The API's public-demo credential permits only registered application/case
  combinations and the server's fixed provider/model. It must reject client
  supplied provider credentials, arbitrary model IDs, and unregistered cases.
- The worker constructs the existing Provider-backed application path. The
  Domain Pack still obtains all numerical/network facts from `gridctl`; the LLM
  only chooses tools and writes the final reader text.
- Provider credentials stay in Railway worker environment variables. They are
  never exposed to the browser, event payloads, reports, or logs.
- The deterministic scripted path remains available for provider-free tests,
  but is no longer the public workbench path.

### Answer and report consistency

- The accepted `answer_output` is the complete LLM answer after current-turn
  result/evidence admission.
- Report rendering continues to read that accepted answer artifact directly;
  it must not create a shorter second summary for the report body.
- Provider failure or timeout produces a visible execution failure and keeps
  already committed turns available; it must not fabricate a fallback answer.

### Automatic stop control

- During automatic execution, the stop button remains visible so the user can
  understand the control, but it is enabled only while the session is `ready`,
  before the next instruction is accepted, and before all instructions are
  complete.
- It is disabled during `pending`, `executing`, and `closing`; the disabled
  control explains that the current operation will finish before stopping.
- Clicking stop at a ready pause point aborts only future automatic submissions;
  it does not cancel an accepted turn or close the session.

## Verification

- Provider-free tests retain scripted application coverage and exact authority
  lineage checks.
- Add frontend tests for the stop button's enabled/disabled states.
- Run local provider-backed pandapower validation with the configured provider,
  then deploy API, worker, and App from the same revision and verify one full
  cloud case, including report answer equality and no credentials in responses.
