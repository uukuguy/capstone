import { describe, expect, it } from 'vitest'
import { parseAttemptRecords } from './attemptRecords'

const page = () => ({
  schema: 'capstone-attempt-records/1', thread_id: 'thr_1', attempt_id: 'attempt_1',
  instruction: 'Explain the previous check', model_context: {
    id: 'ctx_original', model_id: 'ieee39', model_revision: 'rev_1',
    implementation_family: 'pandapower', selection_revision: 'sel_1',
  }, next_after: 9, has_more: false,
  events: [{ event_id: 'evt_9', event_seq: 9, event_type: 'validation_observation', event_version: 1,
    thread_id: 'thr_1', run_id: 'run_1', turn_id: 'turn_1', attempt_id: 'attempt_1',
    model_context_id: 'ctx_original', occurred_at: '2026-10-12T00:00:00Z', visibility: 'public',
    payload: { status: 'failed', message: 'The check failed.' } }],
})

describe('task record identity and pagination', () => {
  it('retains original model identity and failed observations', () => {
    const result = parseAttemptRecords(page(), 'thr_1', 'attempt_1', 0)
    expect(result.modelContext?.modelRevision).toBe('rev_1')
    expect(result.events[0].payload.status).toBe('failed')
    expect(result.nextAfter).toBe(9)
  })
  it.each(['thread', 'attempt', 'cursor', 'foreign_event'])('rejects mismatched %s instead of mixing task records', (kind) => {
    const value = page()
    if (kind === 'thread') value.thread_id = 'thr_other'
    if (kind === 'attempt') value.attempt_id = 'attempt_other'
    if (kind === 'cursor') value.next_after = 8
    if (kind === 'foreign_event') value.events[0].attempt_id = 'attempt_other'
    expect(() => parseAttemptRecords(value, 'thr_1', 'attempt_1', 0)).toThrow()
  })
})
