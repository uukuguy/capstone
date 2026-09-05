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
      request_input_omitted: false,
      omitted_fields: [],
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
    expect(native.request_input_omitted).toBe(false);
    expect(native.omitted_fields).toEqual([]);
  });

  it('models recovery frames with partial state as omitted rather than comparable', () => {
    const recovered: ContextFrame = {
      id: 'context:analysis-test:14',
      source: 'derived',
      source_sequences: [14],
      rule_id: 'context-frame/v1',
      status: 'completed',
      unavailable_reason: 'No following model request',
      source_sequence: 14,
      before_revision: 4,
      after_revision: 5,
      before_state_hash: null,
      after_state_hash: 'sha256:after',
      before_state: null,
      delta: null,
      after_state: { domain_state: { recovered: true } },
      state_omitted: true,
      state_unavailable_reason: 'Context state omitted because it exceeds 128 KiB; context metadata was not inspected.',
      omitted_fields: ['before_state', 'delta'],
      admitted_artifact_refs: ['artifact:context:14'],
      request_input_available: false,
      request_input_unavailable_reason: 'No following model request',
      request_artifact_ref: null,
      max_sequence: 14,
    };

    expect(recovered.state_omitted).toBe(true);
    expect(recovered.delta).toBeNull();
    expect(recovered.admitted_artifact_refs).toEqual(['artifact:context:14']);
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
