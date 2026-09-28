# Provider Turn Performance Design

## Goal

Reduce avoidable provider turns for the five registered demonstration cases.
The provider must still compose published domain tools, preserve current-run
evidence admission, and retain normal recovery behavior. This is a prompt
context optimization, not a deterministic replacement for the agent.

## Root cause

The provider receives the current question and the normal domain policy, but
does not receive the trusted case metadata already known by the application.
For an explicit IEEE-39 case it therefore spends an extra model turn on
`agent_context_get` and `model.list`, and can follow the generic guide's
discovery sequence even when the current instruction only asks for one
calculation. The local trace shows tool execution near one second each while
model decision gaps account for most of the remaining turn time.

## Design

### 1. Neutral prompt decoration seam

Add an optional Kernel-owned prompt decorator. It receives the original
instruction and the one-based turn ordinal, and returns the provider prompt.
The turn controller and reports continue to store the original instruction;
only the provider transport sees the decorated text. Applications without a
decorator keep the current behavior.

### 2. Registered case hints

Each provider worker builds a decorator from its trusted case registration:

- the application and case identifier;
- the registered model origin or model identifier;
- the current turn ordinal;
- the primary published capability IDs for the current turn;
- boundaries: do not discover an already identified model, do not execute
  later case steps, and use another published tool only for an explicit
  prerequisite or recovery error.

Only the current turn's primary capabilities are included. Future questions,
expected values, and answer text are never injected. A provider session with
no registered case keeps the generic prompt unchanged.

### 3. Domain ownership

The Kernel owns the decorator interface and applies it at the provider seam.
The pandapower and PyPSA applications own construction of their case hints
from their registered case documents. No domain semantics or model facts are
added to the Kernel, and authority calls remain unchanged.

### 4. Validation and fallback

Decoration is advisory. It cannot reject a tool call or bypass the authority.
If a tool reports an unknown context, result, or capability, the existing
published recovery guidance remains authoritative. A malformed or unavailable
case document disables decoration for that worker and leaves the generic path
available.

## Verification

- Unit test that the provider receives the decorated current-step prompt while
  the controller records the original instruction.
- Unit test that hints contain only the current step's capability IDs and do
  not contain later instruction text.
- Run the local registered pandapower task once and compare elapsed time,
  model response count, and tool-call count with the existing 48.5-second
  baseline.
- Rebuild local images with `make capstone-local-rebuild`, then upload API and
  worker from the same checkout and verify the cloud health endpoints.
- Run one cloud registered case and compare its timings with the local result.

## Non-goals

- No retry or pre-download changes.
- No deterministic case executor.
- No changes to authority contracts, evidence admission, network diagrams, or
  answer/report schemas.
