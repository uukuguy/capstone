import { describe, expect, it } from 'vitest'
import { projectTaskProgress } from './taskProgress'
import type { EventEnvelope } from './threadProtocol'

const snapshot = (revision: number, text: string) => ({ research_id: 'study', revision, goal: '检查故障影响', condition_refs: [], claims: [], notes: [{ note_id: 'observation', text, refs: ['result:one'] }], open_questions: [] })
const update = (seq: number, attempt: string, revision: number, text: string): EventEnvelope => ({ eventId: `evt_${seq}`, eventSeq: seq, eventType: 'research_state_updated', eventVersion: 1, threadId: 'thread', runId: 'run', attemptId: attempt, occurredAt: '2026-10-13T05:00:00Z', visibility: 'public', payload: { research_id: 'study', research_revision: revision, goal: '检查故障影响', current_note_ids: ['observation'], research_snapshot: snapshot(revision, text) } })

describe('task progress from committed research', () => {
  it('projects explicit tool progress without requiring a research model or making it verified', () => {
    const event = update(1, 'current', 1, 'unused')
    event.eventType = 'tool_completed'
    event.payload = { capability: 'agent_task_progress', ok: true, task_progress: { kind: 'goal', text: '检查故障区域', refs: [] } }
    expect(projectTaskProgress([event], 'current')).toMatchObject([{ kind: 'goal', text: '检查故障区域' }])
    expect(projectTaskProgress([event], 'other')).toEqual([])
  })
  it('retains changed findings and revisions without repeating inherited notes', () => {
    const events = [update(1, 'previous', 1, '原有观察'), update(2, 'current', 2, '原有观察'), update(3, 'current', 3, '发现失供区域'), update(4, 'current', 4, '失供范围修订')]
    const progress = projectTaskProgress(events, 'current')
    expect(progress.map(item => item.text)).toEqual(['发现失供区域', '失供范围修订'])
    expect(progress[1]).toMatchObject({ revision: 4, refs: ['result:one'] })
  })
  it('rejects mismatched public snapshot identity and does not infer tool explanations', () => {
    const event = update(1, 'current', 1, '观察')
    event.payload.research_revision = 9
    expect(projectTaskProgress([event], 'current')).toEqual([])
  })
  it('does not present an inherited snapshot as new progress when earlier history is missing', () => {
    const inherited = update(1, 'current', 2, '原有观察')
    inherited.payload.current_note_ids = []
    expect(projectTaskProgress([inherited], 'current')).toEqual([])
    delete inherited.payload.current_note_ids
    expect(projectTaskProgress([inherited], 'current')).toEqual([])
  })
})
