import { describe, expect, it } from 'vitest'
import {
  parseCommandReceipt, parseEventEnvelope, parseEventPage, parseThreadSnapshot, ThreadProtocolError,
} from './threadProtocol'

function validSnapshot(): Record<string, unknown> {
  return {
    schema: 'capstone-thread-snapshot/1',
    thread_id: 'thr_demo_39',
    run: { run_id: 'run_001', state: 'open' },
    active_model_context: {
      id: 'ctx_ieee39_7', model_id: 'ieee39', model_revision: '7',
      implementation_family: 'pandapower', selection_revision: 'sel_2',
    },
    active_grid_page_id: 'page_ieee39', current_attempt: null,
    last_event_seq: 0, base_event_seq: 0,
  }
}

function event(sequence: number): Record<string, unknown> {
  return {
    event_id: `evt_${sequence}`, event_seq: sequence, event_type: 'attempt_progress',
    event_version: 1, thread_id: 'thr_demo_39', run_id: 'run_001',
    occurred_at: '2026-09-30T00:00:00Z', visibility: 'public', payload: { phase: 'running' },
  }
}

describe('browser Thread protocol parser', () => {
  it('defaults legacy modes and round trips direct runtime identity', () => {
    expect(parseThreadSnapshot(validSnapshot()).runtimeMode).toBe('capstone')
    const snapshot = parseThreadSnapshot({ ...validSnapshot(), runtime_mode: 'pi_reference' })
    expect(snapshot.runtimeMode).toBe('pi_reference')
    expect(snapshot.toDocument().runtime_mode).toBe('pi_reference')
    expect(() => parseThreadSnapshot({ ...validSnapshot(), runtime_mode: 'invalid' })).toThrow('runtime_mode')
  })
  it('preserves uppercase and namespaced registered model IDs in active and pending contexts', () => {
    const document = validSnapshot()
    ;(document.active_model_context as Record<string, unknown>).model_id = 'GBnetwork'
    document.pending_model_switch = { command_id: 'cmd_switch', model_id: 'pypsa-example/model_energy', model_revision: '1', implementation_family: 'pypsa', selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] } }
    const snapshot = parseThreadSnapshot(document)
    expect(snapshot.activeModelContext.modelId).toBe('GBnetwork')
    expect(snapshot.pendingModelSwitch?.modelId).toBe('pypsa-example/model_energy')
    ;(document.active_model_context as Record<string, unknown>).model_id = 'PyPSA/example'
    expect(() => parseThreadSnapshot(document)).toThrow('model_id is invalid')
  })
  it('round trips a verified snapshot', () => {
    const snapshot = parseThreadSnapshot(validSnapshot())

    expect(snapshot.threadId).toBe('thr_demo_39')
    expect(snapshot.activeModelContext.modelRevision).toBe('7')
    expect(snapshot.activeModelContext.enabledProfiles).toEqual([])
    expect(snapshot.toDocument().schema).toBe('capstone-thread-snapshot/1')
  })

  it('parses exact enabled profile references in a model context', () => {
    const document = validSnapshot()
    ;(document.active_model_context as Record<string, unknown>).enabled_profiles = {
      schema: 'capstone-model-capability-selection/1',
      enabled_profiles: [{ profile_id: 'static-analysis', profile_version: '1.0.0' }],
    }
    const snapshot = parseThreadSnapshot(document)
    expect(snapshot.activeModelContext.enabledProfiles).toEqual([
      { profileId: 'static-analysis', profileVersion: '1.0.0' },
    ])
  })

  it('accepts staged model and profile context changes', () => {
    const document = validSnapshot()
    document.pending_model_switch = {
      command_id: 'cmd_switch_006', model_id: 'pypsa39', model_revision: 'revision:sha256:bbbb',
      implementation_family: 'pypsa',
      reason: 'explicit_reopen',
      selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] },
    }
    const snapshot = parseThreadSnapshot(document)
    expect(snapshot.pendingModelSwitch?.modelId).toBe('pypsa39')
    expect(snapshot.pendingModelSwitch?.reason).toBe('explicit_reopen')
    expect(snapshot.toDocument().pending_model_switch).toMatchObject({
      model_id: 'pypsa39', reason: 'explicit_reopen',
    })
  })

  it('omits the default model switch reason while rejecting unknown reasons', () => {
    const document = validSnapshot()
    document.pending_model_switch = {
      command_id: 'cmd_switch_007', model_id: 'pypsa39', model_revision: 'revision:sha256:bbbb',
      implementation_family: 'pypsa',
      selection: { schema: 'capstone-model-capability-selection/1', enabled_profiles: [] },
    }
    const snapshot = parseThreadSnapshot(document)
    expect(snapshot.pendingModelSwitch?.reason).toBeUndefined()
    expect(snapshot.toDocument().pending_model_switch).not.toHaveProperty('reason')

    document.pending_model_switch = {
      ...(document.pending_model_switch as Record<string, unknown>),
      reason: 'unexpected',
    }
    expect(() => parseThreadSnapshot(document)).toThrowError(/reason is invalid/)
  })

  it('rejects an event page gap after the snapshot cursor', () => {
    expect(() => parseEventPage({
      schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
      after_event_seq: 0, next_event_seq: 2, has_more: false,
      events: [event(1), event(3)],
    }, 0)).toThrowError(new ThreadProtocolError('event page is not contiguous'))
  })

  it('rejects fields that could carry credentials or native runtime state', () => {
    const document = { ...validSnapshot(), provider_token: 'secret' }

    expect(() => parseThreadSnapshot(document)).toThrowError(/unknown field/)
  })

  it('rejects a result projection from another Thread or Run', () => {
    const document = validSnapshot()
    document.result_projections = [{
      schema: 'capstone-result-projection/1.0', result_id: 'projection_1',
      result_ref: null, evidence_refs: [], thread_id: 'other_thread', run_id: 'run_001',
      turn_id: 'turn_1', attempt_id: 'attempt_1', model_context_id: 'ctx_ieee39_7',
      model_id: 'ieee39', model_revision: 'revision:sha256:' + 'a'.repeat(64),
      source: { capability_id: 'analysis.powerflow.ac.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
      status: 'unavailable', summary: [], tables: [], element_refs: [], overlay: null,
      unavailable_reason: 'not available',
    }]
    expect(() => parseThreadSnapshot(document)).toThrowError(/identity/)
  })

  it('preserves command identity and status from a receipt', () => {
    const receipt = parseCommandReceipt({
      schema: 'capstone-command-receipt/1', command_id: 'cmd_switch_005',
      idempotency_key: 'idem_switch_005', thread_id: 'thr_demo_39', run_id: 'run_001',
      status: 'accepted', accepted_event_seq: 1,
      target: { model_id: 'pypsa39', model_revision: '3' },
    })

    expect(receipt.commandId).toBe('cmd_switch_005')
    expect(receipt.status).toBe('accepted')
  })

  it('parses one SSE event with the same strict event contract', () => {
    expect(parseEventEnvelope(event(2))).toMatchObject({
      eventId: 'evt_2', eventSeq: 2, threadId: 'thr_demo_39', eventType: 'attempt_progress',
    })
  })

  it('accepts explicit reopen reasons on context activation events', () => {
    const activation = {
      ...event(3),
      event_type: 'model_context_reopened',
      payload: { reason: 'explicit_reopen' },
    }
    const parsed = parseEventEnvelope(activation)
    expect(parsed.payload.reason).toBe('explicit_reopen')

    expect(() => parseEventEnvelope({
      ...activation, payload: { reason: 'unexpected' },
    })).toThrowError(/reason is invalid/)
  })

  it('accepts a saved model workspace activation without treating it as a reopen', () => {
    expect(parseEventEnvelope({
      ...event(5), event_type: 'model_context_activated', payload: { reason: 'model_resume' },
    }).payload.reason).toBe('model_resume')
    expect(() => parseEventEnvelope({
      ...event(5), event_type: 'model_context_reopened', payload: { reason: 'model_resume' },
    })).toThrowError(/reason is invalid/)
  })

  it('replays ordinary model switches before a later explicit reopen', () => {
    const eventPage = parseEventPage({
      schema: 'capstone-thread-events/1', thread_id: 'thr_demo_39',
      after_event_seq: 0, next_event_seq: 4, has_more: false,
      events: [
        { ...event(1), event_type: 'model_context_change_pending', payload: { reason: 'model_switch' } },
        { ...event(2), event_type: 'model_context_activated', payload: { reason: 'model_switch' } },
        { ...event(3), event_type: 'model_context_change_pending', payload: { reason: 'explicit_reopen' } },
        { ...event(4), event_type: 'model_context_reopened', payload: { reason: 'explicit_reopen' } },
      ],
    }, 0)

    expect(eventPage.events.map((item) => item.payload.reason)).toEqual([
      'model_switch', 'model_switch', 'explicit_reopen', 'explicit_reopen',
    ])
    for (const eventType of ['model_context_change_pending', 'model_context_activated', 'model_context_reopened']) {
      expect(() => parseEventEnvelope({
        ...event(5), event_type: eventType, payload: { reason: 'unexpected' },
      })).toThrowError(/reason is invalid/)
    }
    expect(() => parseEventEnvelope({
      ...event(5), event_type: 'model_context_reopened', payload: { reason: 'model_switch' },
    })).toThrowError(/reason is invalid/)
  })
})
