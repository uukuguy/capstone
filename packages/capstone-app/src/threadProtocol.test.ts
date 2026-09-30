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
  it('round trips a verified snapshot', () => {
    const snapshot = parseThreadSnapshot(validSnapshot())

    expect(snapshot.threadId).toBe('thr_demo_39')
    expect(snapshot.activeModelContext.modelRevision).toBe('7')
    expect(snapshot.toDocument().schema).toBe('capstone-thread-snapshot/1')
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
})
