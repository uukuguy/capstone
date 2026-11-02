import { describe, expect, it } from 'vitest'
import { projectResearchBranches, projectTaskProgress, projectTaskStepDiagnostics } from './taskProgress'
import type { EventEnvelope } from './threadProtocol'

const snapshot = (revision: number, text: string) => ({ research_id: 'study', revision, goal: '检查故障影响', condition_refs: [], claims: [], notes: [{ note_id: 'observation', text, refs: ['result:one'] }], open_questions: [] })
const update = (seq: number, attempt: string, revision: number, text: string): EventEnvelope => ({ eventId: `evt_${seq}`, eventSeq: seq, eventType: 'research_state_updated', eventVersion: 1, threadId: 'thread', runId: 'run', attemptId: attempt, occurredAt: '2026-10-13T05:00:00Z', visibility: 'public', payload: { research_id: 'study', research_revision: revision, goal: '检查故障影响', current_note_ids: ['observation'], research_snapshot: snapshot(revision, text) } })

describe('task progress from committed research', () => {
  it('does not render retained runtime dispatch or checkpoint notes from historical events as progress', () => {
    const event = update(1, 'current', 1, 'Coverage is incomplete')
    const state = snapshot(1, 'Coverage is incomplete')
    state.notes.push({ note_id: 'runtime.dispatch.owner.started', text: JSON.stringify({ schema: 'capstone-enterprise-cycle-checkpoint/2', snapshot: 'x'.repeat(21000) }), refs: [] })
    state.notes.push({ note_id: 'runtime.checkpoint.owner.saved', text: '{"phase":"executing"}', refs: [] })
    event.payload.research_snapshot = state
    event.payload.current_note_ids = state.notes.map(note => note.note_id)
    expect(projectTaskProgress([event], 'current').map(item => item.text)).toEqual(['Coverage is incomplete'])
  })
  it('binds real child outcomes to parent call and step without merging reused child IDs', () => {
    const branchEvent = (seq: number, parent: string, type: string, extra = {}) => ({ ...update(seq, 'current', 1, 'unused'), eventType: 'runtime_event', payload: {
      research_branch: { type, subordinate: true, parent_tool_call_id: parent, child_id: 'check', title: '核对省间差异',
        questions: ['差异是否来自缺数？'], expected_outputs: ['缺数核对结论'], owner: { thread_id: 'thread' }, attempt_id: 'current',
        parent_action_id: 'action_one', parent_step_id: 'native-objective_one', checkpoint: { ref: 'checkpoint_one', revision: 2 }, ...extra },
    } })
    const events = [branchEvent(1, 'delegate_one', 'delegation_child_started'),
      branchEvent(2, 'delegate_one', 'delegation_child_tool', { activity: 'tool_execution_end', tool_name: 'read', tool_call_id: 'read_one', is_error: false }),
      branchEvent(3, 'delegate_one', 'delegation_child_finished', { status: 'completed', result_summary: '缺数不足以解释差异' }),
      branchEvent(4, 'delegate_two', 'delegation_child_started')]
    const branches = projectResearchBranches(events, 'current')
    const response = branchEvent(5, 'delegate_one', 'delegation_child_response', { response_number: 1, response_ms: 2300 })
    expect(projectResearchBranches([...events, response, response], 'current')[0].responses).toEqual({ '1': 2300 })
    expect(branches).toHaveLength(2)
    expect(branches[0]).toMatchObject({ parentStepId: 'native-objective_one', status: 'completed', resultSummary: '缺数不足以解释差异', tools: [{ name: 'read', status: 'completed' }] })
    expect(branches[0].durationMs).toBe(0)
    const timed = projectResearchBranches([
      { ...events[0], occurredAt: '2026-10-13T05:00:00Z' },
      { ...events[2], occurredAt: '2026-10-13T05:00:26Z' },
    ], 'current')
    expect(timed[0].durationMs).toBe(26000)
    expect(projectResearchBranches([events[2]], 'current')[0].durationMs).toBeUndefined()
    expect(branches[1].status).toBe('running')
    const failed = projectResearchBranches([
      branchEvent(6, 'delegate_one', 'delegation_child_tool', { activity: 'start', tool_name: 'bash', tool_call_id: 'b1', tool_activity: { operation: 'python analysis.py' } }),
      branchEvent(7, 'delegate_one', 'delegation_child_tool', { activity: 'end', tool_name: 'bash', tool_call_id: 'b1', is_error: true, tool_activity: { output_excerpt: 'ModuleNotFoundError: scipy' } }),
      branchEvent(8, 'delegate_one', 'delegation_child_finished', { status: 'failed', result_summary: '', error: { message: 'Connection reset' } }),
    ], 'current')
    expect(failed[0]).toMatchObject({ status: 'failed', error: 'Connection reset', tools: [{ status: 'failed', operation: 'python analysis.py', output: 'ModuleNotFoundError: scipy' }] })
    expect(projectResearchBranches(events, 'other')).toEqual([])
    expect(projectResearchBranches([{ ...events[0], visibility: 'diagnostic' }], 'current')).toEqual([])
    expect(projectResearchBranches([branchEvent(5, 'delegate_three', 'delegation_child_started', { owner: { thread_id: 'foreign' } })], 'current')).toEqual([])
  })
  it('keeps public step-transition errors visible without inventing an owner', () => {
    const event = update(1, 'current', 1, 'unused')
    event.eventType = 'runtime_event'
    event.payload = { task_step_error: 'Step transition was not applied; the existing step was retained.' }
    expect(projectTaskStepDiagnostics([event], 'current')).toEqual([{ id: 'evt_1', text: event.payload.task_step_error }])
    expect(projectTaskStepDiagnostics([{ ...event, visibility: 'diagnostic' }], 'current')).toEqual([])
    expect(projectTaskStepDiagnostics([event], 'other')).toEqual([])
  })
  it('shows validated native research progress instead of losing it behind bash receipts',()=>{
    const event=update(1,'current',1,'unused')
    event.eventType='runtime_event'
    event.payload={native_type:'tool_execution_end',tool_name:'agent_task_progress',is_error:false,task_progress:{kind:'observation',text:'已核对资料覆盖，接下来比较各区域的变化。',refs:[]}}
    expect(projectTaskProgress([event],'current')).toMatchObject([{text:'已核对资料覆盖，接下来比较各区域的变化。'}])
    expect(projectTaskProgress([{...event,visibility:'diagnostic'}],'current')).toEqual([])
    expect(projectTaskProgress([{...event,payload:{...event.payload,is_error:true}}],'current')).toEqual([])
  })
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
