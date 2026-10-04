# Capstone M10 Registered PyPSA Topology Provider

## Purpose

Expose the topology of the active registered PyPSA model in the unified Thread
model pane. The topology must come from the registered Authority through the
PyPSA Domain Pack and must remain bound to the active model context.

## Scope

The initial slice covers:

- a generic PyPSA `operator.diagram` reader for any registered model;
- a bounded application seam that supplies the reader to the neutral Thread
  worker without importing PyPSA into the Kernel;
- normalized `capstone-network-diagram/1.0` and
  `capstone-network-layer/1.0` events in Thread replay;
- current-model Web rendering and safe scalar element focus;
- provider-free Authority, worker, replay, and Web regression coverage.

The slice does not add automatic coordinates, arbitrary uploaded networks,
raw time-series overlays, result-to-topology joins beyond admitted scalar
element references, or TUI image rendering.

## Ownership and data flow

1. The PyPSA Authority receives the registered model reference through the
   Domain Pack's `operator.diagram` capability and returns a bounded topology
   projection. The Authority remains responsible for model contents,
   coordinates, component identity, and revision.
2. The PyPSA application prepares a model-context-bound diagram provider. The
   provider verifies that the Authority response model reference maps to the
   immutable Thread model revision and converts it to the shared diagram
   contract. It does not accept a case ID.
3. The neutral Harness/Thread worker invokes the optional provider after an
   Attempt commits. It validates the returned diagram and layer, binds both to
   the Attempt's model context and revision, and appends ordered public
   `network_diagram` and `network_layer` events. Provider failure emits the
   existing unavailable signal and does not alter answer admission.
4. The API replays the events through the existing Thread event page. The Web
   projection store keeps the latest diagram and layer for each active model
   context. The model pane displays only a diagram whose model revision equals
   the active context; historical pages stay read-only.
5. Result projection focus is accepted only when the element ID exists in the
   current diagram and the result model revision equals the diagram revision.
   No generic layer may invent topology, coordinates, metrics, or references.

## Neutral seam

The Kernel exposes a small optional provider contract for a bounded Thread
network projection. The contract accepts the claimed Attempt, admitted result
and evidence references, and the observed tool events. It returns a mapping
that is already owned by the application and is checked again by the neutral
worker. The provider is injected by the application assembly and is absent for
applications without a registered topology authority.

The neutral worker owns event sequencing and failure handling. It does not
select capabilities, inspect Domain Pack state, import PyPSA, or call a
caller-selected endpoint. The PyPSA provider obtains its executor and model
binding from the prepared application context.

## Public event contract

- `network_diagram` carries one normalized `capstone-network-diagram/1.0`
  document. Its model revision and fingerprint are stable for the registered
  model revision.
- `network_layer` carries one normalized
  `capstone-network-layer/1.0` document with the matching diagram reference,
  model revision, ordinal, focus IDs, next-focus IDs, and optional admitted
  overlay.
- Events include the existing Thread event identity fields, including
  `attempt_id` and `model_context_id`. They are replayable and validated on
  restore.
- A missing or invalid diagram produces a typed unavailable event. It never
  produces a fabricated fallback topology.

## Web behavior

The Thread projection store records the most recent diagram and layer for the
active model context while retaining event order. The model pane uses the
event-backed diagram before any optional preview. On a model switch, the new
context starts without the previous model's diagram until a matching event
arrives. A historical page never mutates the active page or accepts focus.

Safe focus checks the current diagram's bus and branch IDs, the active model
ID, and the exact model revision. If any check fails, the UI keeps the result
card readable and declines topology focus.

## Failure handling

- Authority unavailable, malformed, oversized, or revision-mismatched output:
  emit unavailable state and retain the committed answer.
- Event replay gap or identity mismatch: use the existing resync path.
- Missing coordinates: preserve the Authority's declared schematic state;
  never synthesize geographic coordinates.
- A result overlay with a non-admitted reference or foreign revision is
  rejected by the existing network normalization contract.

## Verification plan

Tests are written before production changes and must first fail for the new
behavior:

1. Authority/provider tests verify arbitrary registered-model diagrams,
   complete topology beyond model-tool limits, and revision mismatch rejection.
2. Neutral worker tests verify provider event ordering, unavailable fallback,
   and replay identity binding.
3. PyPSA provider-free Thread tests verify a real registered model emits a
   diagram after a committed Attempt and that a second model replaces the
   active page without leaking the first revision.
4. Web tests verify parsing, current-model selection, historical read-only
   behavior, and safe focus against dynamic diagram IDs.
5. Run focused package tests, App tests/build, Pyright, E2E, and the current
   source local rebuild before independent review.

## Deferred work

Topology provider work remains separate from result projection semantics. This
slice does not make PyPSA operations overlays automatic; only already admitted
scalar references may be rendered on a matching diagram.
