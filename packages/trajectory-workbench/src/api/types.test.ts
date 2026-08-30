import { describe, expect, expectTypeOf, it } from 'vitest';
import type { ApplicationMetadata, BindingMetadata, ContextFrame, ContextState, DomainPayloadView } from './types';

describe('ContextFrame API contract', () => {
  it('models recursive JSON state and the legacy missing-request invariant', () => {
    const native: ContextFrame = {
      id: 'context:analysis-test:12',
      source: 'derived',
      source_sequences: [12],
      rule_id: 'context-frame/v1',
      status: 'completed',
      unavailable_reason: null,
      source_sequence: 12,
      before_revision: 3,
      after_revision: 4,
      before_state_hash: 'sha256:before',
      after_state_hash: 'sha256:after',
      before_state: { domain_state: { calculations: ['result:1'] } },
      delta: { domain_state: { calculations: { added: ['result:2'] } } },
      after_state: { domain_state: { calculations: ['result:1', 'result:2'] } },
      request_input_available: true,
      request_input_unavailable_reason: null,
      request_artifact_ref: 'artifact:request:13',
      max_sequence: 13,
    };
    const legacy: ContextFrame = {
      ...native,
      request_artifact_ref: null,
      unavailable_reason: 'legacy source did not capture model request input',
      request_input_available: false,
      request_input_unavailable_reason: 'legacy source did not capture model request input',
    };

    expectTypeOf(native.before_state).toEqualTypeOf<ContextState>();
    expectTypeOf(legacy.unavailable_reason).toEqualTypeOf<string>();
  });

  it('models application-local bindings without assuming a grid authority', () => {
    const binding: BindingMetadata = {
      binding_id: 'inventory',
      domain_id: 'inventory-readonly',
      domain_version: '1.0.0',
      authority_id: 'inventory-api',
      schema: 'inventory-output/1.0',
      presentation: { business_title: 'Inventory review' },
    };
    const application: ApplicationMetadata = {
      application_id: 'inventory-review',
      application_version: '2.0.0',
      bindings: { inventory: binding },
    };
    const payload: DomainPayloadView = {
      binding_id: 'inventory',
      domain_id: 'inventory-readonly',
      authority_id: 'inventory-api',
      schema: 'inventory-output/1.0',
      payload: { items: [{ sku: 'A-1', available: 4 }] },
      interpretation: 'opaque',
    };

    expect(application.bindings.inventory.authority_id).toBe('inventory-api');
    expect(payload.payload.items).toBeDefined();
  });
});
