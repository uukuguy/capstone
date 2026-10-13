import { describe, expect, it } from 'vitest'
import { projectTaskProgress } from './taskProgress'
import type { EventEnvelope } from './threadProtocol'

const snapshot = (revision: number, text: string) => ({ research_id: 'study', revision, goal: '检查故障影响', condition_refs: [], claims: [], notes: [{ note_id: 'observation', text, refs: ['result:one'] }], open_questions: [] })
const update = (seq: number, attempt: string, revision: number, text: string): EventEnvelope => ({ eventId: `evt_${seq}`, eventSeq: seq, eventType: 'research_state_updated', eventVersion: 1, threadId: 'thread', runId: 'run', attemptId: attempt, occurredAt: '2026-10-13T05:00:00Z', visibility: 'public', payload: { research_id: 'study', research_revision: revision, goal: '检查故障影响', research_snapshot: snapshot(revision, text) } })

describe('task progress from committed research', () => {
  it('retains changed findings and revisions without repeating inherited notes', () => {
    const events = [update(1, 'previous', 1, '原有观察'), update(2, 'current', 2, '原有观察'), update(3, 'current', 3, '发现失供区域'), update(4, 'current', 4, '失供范围修订')]
    const progress = projectTaskProgress(events, 'current')
    expect(progress.map(item => item.text)).toEqual(['发现失供区域', '失供范围修订'])
    expect(progress[1]).toMatchObject({ revision: 4, refs: ['result:one'], replaces: 'evt_3:observation' })
  })
  it('rejects mismatched public snapshot identity and does not infer tool explanations', () => {
    const event = update(1, 'current', 1, '观察')
    event.payload.research_revision = 9
    expect(projectTaskProgress([event], 'current')).toEqual([])
  })
})
