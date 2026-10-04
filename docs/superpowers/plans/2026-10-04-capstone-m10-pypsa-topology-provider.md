# Capstone M10 Registered PyPSA Topology Provider

## Goal

Make a registered PyPSA model's topology available in the unified Thread model
pane through the existing `capstone-network-diagram/1.0` and
`capstone-network-view/2.0` contracts. The provider must work for the active
model context, not only for a scripted business case.

## Boundary

- The PyPSA Authority/Domain Pack owns the semantic `operator.diagram` action
  and returns a bounded diagram projection; raw PyPSA `Network` objects never
  cross the worker boundary.
- The projection is bound to the active `pypsa-model` reference and public
  model revision before it is emitted as Thread events.
- The shared Kernel/Thread worker owns event sequencing and admission checks;
  the Web reuses the existing `NetworkView` and model-page surface.
- Element focus and overlays are admitted only when their model revision,
  diagram identity, and current-run evidence agree. Missing topology remains a
  visible unavailable state.
- The existing PyPSA business-case diagram path remains compatible but is not
  used as the generic model provider.

## Initial slice

1. Publish a bounded PyPSA topology capability for registered models.
2. Add an application-owned network reader for the active model context.
3. Emit normalized diagram/layer events from the unified Thread worker.
4. Display the active model diagram and safe element focus in the existing Web
   pane; keep one page per model and historical pages read-only.
5. Add provider-free authority, worker, Thread replay, and Web regression
   coverage, followed by an independent M10 code review.

## Explicitly deferred

- automatic geographic coordinates when the authority does not publish them;
- arbitrary user-uploaded networks;
- raw time-series overlays and result-card-to-topology joins beyond admitted
  scalar element references;
- TUI image rendering changes.
