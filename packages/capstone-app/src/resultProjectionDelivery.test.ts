import { describe, expect, it } from 'vitest'
import { ResultProjectionDelivery } from './resultProjectionDelivery'
import type { EventEnvelope } from './threadProtocol'

const projection = {
  schema: 'capstone-result-projection/1.0', result_id: 'result_1',
  result_ref: `result:sha256:${'a'.repeat(64)}`, evidence_refs: [`evidence:sha256:${'b'.repeat(64)}`],
  thread_id: 'thr_1', run_id: 'run_1', turn_id: 'turn_1', attempt_id: 'attempt_1',
  model_context_id: 'ctx_1', model_id: 'ieee39', model_revision: `revision:sha256:${'c'.repeat(64)}`,
  source: { capability_id: 'analysis.run', domain_pack_id: 'pandapower-static-analysis', implementation_family: 'pandapower' },
  status: 'partial', summary: [], tables: [], element_refs: [], overlay: null,
}

function event(type: string, payload: Record<string, unknown>): EventEnvelope {
  return { eventId: 'evt_1', eventSeq: 1, eventVersion: 1, eventType: type, threadId: 'thr_1',
    runId: 'run_1', turnId: 'turn_1', attemptId: 'attempt_1', modelContextId: 'ctx_1',
    selectionRevision: 'sel_1', occurredAt: '2026-10-12T00:00:00Z', visibility: 'public', payload }
}

function terminal(): EventEnvelope {
  return event('attempt_failed', { result_projection_manifest: [{ result_id: 'result_1', parts: 2 }],
    result_refs: [projection.result_ref], evidence_refs: projection.evidence_refs,
    admission: { mode: 'authority_backed', assurance: 'lineage_verified' } })
}

function part(index: number): EventEnvelope {
  const data = JSON.stringify(projection)
  return event('result_projection_part', { result_id: 'result_1', parts: 2, part_index: index,
    data: index === 0 ? data.slice(0, 100) : data.slice(100) })
}

describe('result delivery', () => {
  it('keeps verified partial data from a failed task and consumes its parts once', () => {
    const delivery = new ResultProjectionDelivery()
    delivery.accept(part(0))
    delivery.accept(part(1))
    expect(delivery.complete(terminal())).toEqual([projection])
    expect(() => delivery.complete(terminal())).toThrow('incomplete')
  })

  it.each(['missing', 'wrong-attempt', 'missing-evidence', 'unverified', 'duplicate'])('rejects %s delivery', (failure) => {
    const delivery = new ResultProjectionDelivery()
    delivery.accept(part(0))
    if (failure !== 'missing') delivery.accept(part(1))
    const completed = terminal()
    if (failure === 'wrong-attempt') completed.attemptId = 'other_attempt'
    if (failure === 'missing-evidence') completed.payload.evidence_refs = []
    if (failure === 'unverified') completed.payload.admission = { mode: 'limited', assurance: 'limited' }
    if (failure === 'duplicate') completed.payload.result_projection_manifest = [
      { result_id: 'result_1', parts: 2 }, { result_id: 'result_1', parts: 2 },
    ]
    expect(() => delivery.complete(completed)).toThrow()
  })

  it('rejects an out-of-order part before buffering it', () => {
    expect(() => new ResultProjectionDelivery().accept(part(1))).toThrow('do not match')
  })

  it('accepts at most 4000 Unicode code points per part, including astral characters', () => {
    const delivery = new ResultProjectionDelivery()
    delivery.accept(event('result_projection_part', { result_id: 'result_1', parts: 2, part_index: 0, data: '🔬'.repeat(4000) }))
    expect(() => delivery.accept(event('result_projection_part', {
      result_id: 'result_1', parts: 2, part_index: 1, data: '🔬'.repeat(4001),
    }))).toThrow('invalid')
  })
})
