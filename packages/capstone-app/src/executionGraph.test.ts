import { describe, expect, it } from 'vitest'
import { projectExecutionGraph } from './executionGraph'
import type { EventEnvelope } from './threadProtocol'

export const owner = { thread_id: 'thread', work_id: 'work', research_id: 'research', goal_revision: 1 }
export const node = (id: string, depends_on: string[] = [], phase = 'ready') => ({ id, purpose: `Question ${id}`, questions: [`Why ${id}?`], checks: ['check'], depends_on, expected_outputs: ['answer'], mode: 'execute', execution: 'delegated', instruction: 'Examine', outputs: [{ slot: 'answer', kind: 'observation', description: 'answer' }], inputs: [], phase, applicability: 'current', execution_revision: 1, execute_action_id: phase === 'ready' || phase === 'pending' ? null : `action:${id}`, assess_action_id: null, input_bindings: [], output_bindings: [], blocked_by: depends_on, wait_reason: depends_on.length ? 'dependencies' : null, settled_status: null })
export const action = (id: string, revision = 1) => ({ id: `action:${id}`, owner, attempt_id: 'attempt', step_id: id, kind: 'execute', definition_ref: `node:${id}`, execution_revision: revision, graph_ref: 'graph:1', graph_revision: 1, input_bindings: [] })
export const graph = (nodes = [node('A', [], 'executing'), node('B', [], 'executing'), node('C', ['A'], 'pending'), node('D', ['A', 'B'], 'pending')]) => ({ schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:1', graph_revision: 1, goal: 'Explain the differences', output_mode: 'text', model_revision_reason: null, nodes, actions: nodes.filter(n => n.execute_action_id).map(n => action(n.id)), results: [] as Record<string, unknown>[] })
export const event = (seq: number, payload: Record<string, unknown>): EventEnvelope => ({ eventId: `event:${seq}`, eventSeq: seq, eventType: 'runtime_event', eventVersion: 1, threadId: 'thread', runId: 'run', attemptId: 'attempt', occurredAt: `2026-10-21T00:00:${String(seq).padStart(2, '0')}Z`, visibility: 'public', payload })
export const progress = (seq: number, value = graph(), extras = {}) => event(seq, { research_graph: { type: 'enterprise_graph_progress', owner, attempt_id: 'attempt', task_id: 'task', checkpoint: { ref: `checkpoint:${seq}`, revision: seq }, graph: value, events: [], ...extras } })
export const frame = (seq: number, type: string, step = 'A', extras = {}) => event(seq, { research_graph_event: { type, owner, attempt_id: 'attempt', task_id: 'task', action_id: `action:${step}`, step_id: step, checkpoint: { ref: 'checkpoint:1', revision: 1 }, ...(type.includes('child') ? { child_id: step } : {}), ...extras } })
export const result = (ref = 'result:A:1', revision = 1) => ({ schema: 'capstone-task-result/1', result_ref: ref, producer: { step_id: 'A', action_id: revision === 1 ? 'action:A' : 'action:A2', execution_revision: revision, attempt_id: 'attempt' }, slot: 'answer', kind: 'observation', summary: 'Same bytes', scope: 'selected rows', consumed_results: [], source_versions: [{ ref: 'source:one', revision: 'v1' }], method: { ref: 'method:one', revision: 'v1', environment_unavailable: 'not supplied' }, supersedes: revision === 1 ? [] : ['result:A:1'], recompute_reason: revision === 1 ? null : { kind: 'discrepancy', refs: ['source:one'], diagnostic: 'Recheck' } })

describe('exact execution graph projection', () => {
  it('retains model request starts and exact tool IDs across interleaved tasks and replay', () => {
    const rows = [progress(1),
      frame(2, 'enterprise_graph_child_response_started', 'A', { response_number: 1 }),
      frame(3, 'enterprise_graph_child_response', 'B', { response_number: 1, response_ms: 10, tool_call_ids: ['call:B'] }),
      frame(4, 'enterprise_graph_child_response', 'A', { response_number: 1, response_ms: 2000, tool_call_ids: ['call:A1', 'call:A2'], stop_reason: 'toolUse' }),
      frame(5, 'enterprise_graph_child_response', 'A', { response_number: 2, response_ms: 20, tool_call_ids: [], stop_reason: 'stop' }),
      frame(6, 'enterprise_graph_child_response_started', 'B', { response_number: 2 })]
    const value=projectExecutionGraph([...rows, rows[3], rows[1]], 'attempt')!
    expect(value.executions[0].responses).toMatchObject([
      { number: 1, ms: 2000, toolCallIds: ['call:A1', 'call:A2'], startedAt: '2026-10-21T00:00:02Z', finishedAt: '2026-10-21T00:00:04Z', stopReason: 'toolUse' },
      { number: 2, ms: 20, toolCallIds: [], stopReason: 'stop' }])
    expect(value.executions[1].responses).toMatchObject([{ number: 1, toolCallIds: ['call:B'] }, { number: 2, ms: 0, startedAt: '2026-10-21T00:00:06Z' }])
  })
  it('keeps native tool execution time separate from the observed record interval', () => {
    const p = projectExecutionGraph([progress(1),
      frame(2, 'enterprise_graph_tool_binding', 'A', { tool_call_id: 'call:A', tool_name: 'bash' }),
      frame(3, 'enterprise_graph_child_tool', 'A', { activity: 'start', tool_call_id: 'call:A', tool_name: 'bash' }),
      frame(13, 'enterprise_graph_child_tool', 'A', { activity: 'end', tool_call_id: 'call:A', tool_name: 'bash', execution_ms: 2710.25 }),
    ], 'attempt')!
    expect(p.executions[0].tools[0]).toMatchObject({ durationMs: 10000, executionMs: 2710.25 })
  })
  it('retains public parent request timing, including errors, without inventing node usage', () => {
    const runtime = (seq: number, phase: string, extra = {}): EventEnvelope => ({ ...event(seq, { runtime_mode: 'capstone', phase, ...extra }), eventType: 'runtime_action' })
    const rows: EventEnvelope[] = [progress(1), runtime(2, 'started'), runtime(4, 'response_completed', { response_kind: 'tools' }),
      runtime(5, 'started'), runtime(8, 'response_completed', { response_kind: 'error' }), runtime(9, 'completed'),
      runtime(10, 'started', { task_step: { id: 'finalization' } }), runtime(12, 'response_completed', { response_kind: 'text' }),
      { ...runtime(13, 'started'), attemptId: 'other' }, runtime(15, 'response_completed', { response_kind: 'text' }),
      { ...runtime(16, 'started'), visibility: 'diagnostic' }, runtime(18, 'response_completed', { response_kind: 'text' })]
    const projected = projectExecutionGraph([...rows, rows[2]], 'attempt')!
    expect(projected.parentResponses).toMatchObject([{ ms: 2000, kind: 'tools' }, { ms: 3000, kind: 'error' }])
    expect(projected.executions.every(e => e.responses.length === 0)).toBe(true)
    expect(projectExecutionGraph(rows, 'attempt')!.parentResponses).toEqual(projected.parentResponses)
  })
  it('retains a currently running public main request until its response arrives', () => {
    const start = { ...event(2, {runtime_mode:'capstone',phase:'started'}), eventType:'runtime_action' } as EventEnvelope
    expect(projectExecutionGraph([progress(1),start], 'attempt')!.parentPendingResponse).toMatchObject({id:start.eventId,startedAt:start.occurredAt})
    const end = { ...event(4, {runtime_mode:'capstone',phase:'response_completed',response_kind:'text'}),eventType:'runtime_action' } as EventEnvelope
    expect(projectExecutionGraph([progress(1),start,end], 'attempt')!.parentPendingResponse).toBeUndefined()
  })
  it('times only exact declared execution events without assigning parent model usage', () => {
    const g = graph(); g.nodes[0].execution = 'parent'
    const started = { kind: 'node_started', step_id: 'A', action_id: 'action:A', execution_revision: 1 }
    const settled = { ...started, kind: 'node_execution_settled', settled_status: 'completed' }
    const p = projectExecutionGraph([progress(1, g, { events: [started] }),
      progress(2, g, { events: [{ ...settled, step_id: 'B' }] }),
      progress(3, g, { events: [{ ...settled, execution_revision: 2 }] }),
      progress(5, g, { events: [settled] })], 'attempt')!
    expect(p.executions[0]).toMatchObject({ executionStartedAt: '2026-10-21T00:00:01Z', executionFinishedAt: '2026-10-21T00:00:05Z', executionIntervalMs: 4000 })
    expect(p.executions[0].responses).toEqual([])
    expect(p.executions[0].durationMs).toBeUndefined()
    expect(p.executions[1].executionIntervalMs).toBeUndefined()
    const interrupted = projectExecutionGraph([progress(1, g, { events: [started] })], 'attempt')!
    expect(interrupted.executions[0].executionIntervalMs).toBeUndefined()
  })
  it('binds recorded and assessed control tools to their exact retained node actions', () => {
    const first = graph(), recorded = structuredClone(first), assessed = structuredClone(first)
    const assessment = { ...action('A'), id: 'assess:A', kind: 'assess' }
    Object.assign(recorded.nodes[0], { phase: 'recorded', assess_action_id: assessment.id })
    recorded.actions = [assessment, action('B')]
    Object.assign(assessed.nodes[0], { phase: 'success', assess_action_id: assessment.id })
    assessed.actions = [action('B')]
    const p = projectExecutionGraph([progress(1, first), progress(2, recorded, { action_id: 'action:A', control: { tool_call_id: 'record:one', tool_name: 'agent_research_record' } }),
      progress(3, assessed, { action_id: assessment.id, control: { tool_call_id: 'assess:one', tool_name: 'agent_research_assess' } }),
      event(4, { task_id: 'task', tool_call_id: 'record:one', tool_name: 'agent_research_record', native_type: 'tool_execution_end', is_error: false }),
      event(5, { task_id: 'task', tool_call_id: 'assess:one', tool_name: 'agent_research_assess', native_type: 'tool_execution_end', is_error: false })], 'attempt')!
    expect(p.executions.find(e => e.action.id === 'action:A')!.tools).toMatchObject([
      { id: 'record:one', actionId: 'action:A', name: 'agent_research_record' }, { id: 'assess:one', actionId: 'assess:A', name: 'agent_research_assess' }])
    expect(p.executions.find(e => e.action.id === 'action:B')!.tools).toHaveLength(0)
    expect(p.controlCalls).toMatchObject([{ actionId: 'action:A', stepId: 'A' }, { actionId: 'assess:A', stepId: 'A' }])
  })
  it.each([
    { source_refs: ['/private/source.csv'], selected_source_versions: [] },
    { source_refs: ['source:one', 'source:one'], selected_source_versions: [] },
    { source_refs: [], selected_source_versions: [{ ref: 'source:one', revision: 'v1' }] },
    { source_refs: ['source:one'], selected_source_versions: [{ ref: 'source:one', revision: null }] },
    { source_refs: ['source:one'], selected_source_versions: [{ ref: 'source:one', revision: ['v1'] }] },
  ])('rejects malformed or unselected raw source scope %j', scope => {
    const value = graph()
    Object.assign(value.nodes[0], scope)
    expect(projectExecutionGraph([progress(1, value)], 'attempt')).toBeUndefined()
  })
  it('rejects a current action with a source grant different from its selected node', () => {
    const value = graph()
    Object.assign(value.nodes[0], { source_refs: ['source:one'], selected_source_versions: [{ ref: 'source:one', revision: 'v1' }] })
    Object.assign(value.actions[0], { source_refs: ['source:other'], source_versions: [{ ref: 'source:other', revision: 'v1' }] })
    expect(projectExecutionGraph([progress(1, value)], 'attempt')).toBeUndefined()
  })
  it('links only explicit immutable control call IDs to their committed graph versions', () => {
    const p = projectExecutionGraph([progress(1, graph(), { control: { tool_call_id: 'plan:one', tool_name: 'agent_research_plan' } }), progress(2), progress(3, graph(), { control: { tool_call_id: 'plan:one', tool_name: 'agent_research_revise' } })], 'attempt')!
    expect(p.controlCalls).toMatchObject([{ callId: 'plan:one', name: 'agent_research_plan', graphRef: 'graph:1', checkpoint: { ref: 'checkpoint:1', revision: 1 } }])
    expect(p.checkpoints).toHaveLength(2)
  })
  it('shows concurrent A/B and releases C after accepted A while D waits for B', () => {
    const first = graph()
    const second = structuredClone(first)
    Object.assign(second.nodes[0], { phase: 'success', settled_status: 'completed', output_bindings: [{ slot: 'answer', kind: 'observation', result_ref: 'result:A:1' }] })
    Object.assign(second.nodes[2], { phase: 'executing', execute_action_id: 'action:C', blocked_by: [], wait_reason: null })
    second.nodes[3].blocked_by = ['B']
    second.actions.push(action('C')); second.results = [result()]
    const projected = projectExecutionGraph([progress(1, first), progress(2, second)], 'attempt')!
    expect(projected.current.nodes.map(n => [n.id, n.phase, n.blocked_by])).toEqual([['A', 'success', []], ['B', 'executing', []], ['C', 'executing', []], ['D', 'pending', ['B']]])
    expect(projected.current.nodes[3].depends_on).toEqual(['A', 'B'])
  })
  it('binds preceding native tools by call ID and retains late tools on their original execution', () => {
    const events = [progress(1), event(2, { native_type: 'tool_execution_start', task_id: 'task', tool_name: 'read', tool_call_id: 'call:A' }), frame(3, 'enterprise_graph_tool_binding', 'A', { tool_call_id: 'call:A', tool_name: 'read' }), frame(4, 'enterprise_graph_child_tool', 'B', { activity: 'start', tool_call_id: 'call:B', tool_name: 'bash' }), frame(5, 'enterprise_graph_child_finished', 'B', { status: 'completed', result_summary: 'B returned' }), event(6, { native_type: 'tool_execution_end', task_id: 'task', tool_name: 'read', tool_call_id: 'call:A', activity: { output_excerpt: 'A output' } })]
    const p = projectExecutionGraph(events, 'attempt')!
    expect(p.executions.find(e => e.action.id === 'action:A')!.tools).toMatchObject([{ id: 'call:A', name: 'read', status: 'completed', durationMs: 4000, output: 'A output' }])
    expect(p.executions.find(e => e.action.id === 'action:B')!.tools).toMatchObject([{ id: 'call:B', name: 'bash' }])
    const reassignment = frame(7, 'enterprise_graph_tool_binding', 'B', { tool_call_id: 'call:A', tool_name: 'read' })
    expect(projectExecutionGraph([...events, reassignment], 'attempt')!.executions.find(e => e.action.id === 'action:B')!.tools).toHaveLength(1)
  })
  it('keeps immutable same-byte result versions and the actual old consumer binding after revision', () => {
    const first = graph(); first.results = [result()]
    Object.assign(first.nodes[2], { phase: 'executing', execute_action_id: 'action:C', input_bindings: [{ input_name: 'data', result_ref: 'result:A:1', producer_step_id: 'A', slot: 'answer' }] }); first.actions.push({ ...action('C'), input_bindings: first.nodes[2].input_bindings })
    const next = structuredClone(first); next.graph_ref = 'graph:2'; next.graph_revision = 2; next.model_revision_reason = 'Changed source' as never
    next.results.push(result('result:A:2', 2)); Object.assign(next.nodes[0], { execution_revision: 2, execute_action_id: 'action:A2', assess_action_id: 'assess:A2', phase: 'recorded' }); next.actions = [action('B'), first.actions[2], { ...action('A', 2), id: 'assess:A2', kind: 'assess', graph_ref: 'graph:2', graph_revision: 2 }]; next.nodes[2].applicability = 'stale'
    const p = projectExecutionGraph([progress(1, first), progress(2, next), frame(3, 'enterprise_graph_child_finished', 'C', { status: 'completed' })], 'attempt')!
    expect(p.current.results.map(r => r.result_ref)).toEqual(['result:A:1', 'result:A:2'])
    expect(p.current.nodes[2].input_bindings[0].result_ref).toBe('result:A:1')
    expect(p.current.nodes[2].applicability).toBe('stale')
    expect(p.revisions.map(r => r.graph.graph_ref)).toEqual(['graph:1', 'graph:2'])
    expect(p.executions.find(e => e.action.id === 'action:C')!.nativeStatus).toBe('completed')
  })
  it('keeps native unknown separate from recorded and never invents model response timing', () => {
    const value = graph(); Object.assign(value.nodes[0], { phase: 'recorded', assess_action_id: 'assess:A', settled_status: 'unknown' }); value.actions = [{ ...action('A'), id: 'assess:A', kind: 'assess' }, action('B')]
    const p = projectExecutionGraph([progress(1), progress(2, value), frame(3, 'enterprise_graph_child_finished', 'A', { status: 'unknown' })], 'attempt')!
    expect(p.current.nodes[0].phase).toBe('recorded'); expect(p.executions[0].nativeStatus).toBe('unknown')
    expect(p.executions[0].responses).toEqual([]); expect(p.executions[0].durationMs).toBeUndefined()
  })
  it('uses the checked SDK count fields and keeps response timing only for observed response IDs', () => {
    const p = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_child_started'), frame(3, 'enterprise_graph_child_response', 'A', { response_number: 1, response_ms: 120, usage: { totalTokens: 42 } }), frame(4, 'enterprise_graph_child_finished', 'A', { status: 'completed', model_responses: 2, turns: 3 })], 'attempt')!
    expect(p.executions[0]).toMatchObject({ modelResponseCount: 2, turnCount: 3, durationMs: 2000, responses: [{ number: 1, ms: 120, usage: { totalTokens: 42 } }] })
  })
  it('rejects bad ownership, schema, checkpoint, cycles, unknown actions, duplicate IDs and mutated leases', () => {
    const initial = progress(1)
    const bad = [progress(2, graph(), { owner: { ...owner, thread_id: 'other' } }), progress(3, { ...graph(), schema: 'old' }), progress(4, graph(), { checkpoint: { ref: 'bad', revision: 0 } }), progress(5, graph([node('A', ['B']), node('B', ['A'])])), progress(6, graph([node('A'), node('A')])), progress(7, graph(), { action_id: 'unknown' }), progress(8, { ...graph(), actions: [{ ...action('A'), step_id: 'B' }] }), frame(9, 'enterprise_graph_child_started', 'unknown'), { ...frame(10, 'enterprise_graph_child_started'), threadId: 'other' }]
    const p = projectExecutionGraph([initial, ...bad], 'attempt')!
    expect(p.checkpoints).toHaveLength(1); expect(p.executions.every(e => !e.startedAt)).toBe(true)
    const changed = graph(); changed.results = [result()]
    const changedAgain = structuredClone(changed); changedAgain.results[0].summary = 'changed immutable result'
    expect(projectExecutionGraph([progress(1, changed), progress(2, changedAgain)], 'attempt')!.checkpoints).toHaveLength(1)
    expect(projectExecutionGraph([{ ...initial, visibility: 'diagnostic' }], 'attempt')).toBeUndefined()
  })
  it('rejects a changed original node/action binding even when the active action list omits that action', () => {
    const next = graph(); next.actions = [action('B')]; next.nodes[0].execution_revision = 2
    expect(projectExecutionGraph([progress(1), progress(2, next)], 'attempt')!.checkpoints).toHaveLength(1)
  })
  it('does not replay a duplicate checkpoint with changed metadata or duplicate child settlement', () => {
    const events = [progress(1), progress(1, graph(), { events: [{ kind: 'graph_delivery_committed', summary: 'forged duplicate' }] }), frame(2, 'enterprise_graph_child_started'), frame(3, 'enterprise_graph_child_finished', 'A', { status: 'completed' }), frame(4, 'enterprise_graph_child_finished', 'A', { status: 'failed', result_summary: 'changed duplicate' })]
    const p = projectExecutionGraph(events, 'attempt')!
    expect(p.controlEvents).toEqual([])
    expect(p.executions[0].nativeStatus).toBe('completed')
    expect(p.executions[0].resultSummary).toBeUndefined()
  })
  it('does not treat a malformed child tool activity as an immutable tool binding', () => {
    const p = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_child_tool', 'B', { activity: 'invalid', tool_call_id: 'call:A', tool_name: 'read' }), frame(3, 'enterprise_graph_tool_binding', 'A', { tool_call_id: 'call:A', tool_name: 'read' }), event(4, { native_type: 'tool_execution_start', task_id: 'task', tool_name: 'read', tool_call_id: 'call:A' })], 'attempt')!
    expect(p.executions.find(e => e.action.id === 'action:A')!.tools).toHaveLength(1)
    expect(p.executions.find(e => e.action.id === 'action:B')!.tools).toHaveLength(0)
  })
})

describe('malformed graph binding admission', () => {
  const malformed = [{ bad: true }, ['bad'], 42, null, '', 'invalid name']
  for (const field of ['input_name', 'producer_step_id']) {
    for (const location of ['node', 'action']) {
      it.each(malformed.map(value => ({ value })))(`rejects malformed ${location} ${field}: %j and retains the preceding snapshot`, ({ value }) => {
        const invalid = graph()
        const binding = { result_ref: 'result:old', slot: 'answer', [field]: value }
        Object.assign(location === 'node' ? invalid.nodes[0] : invalid.actions[0], { input_bindings: [binding] })
        expect(projectExecutionGraph([progress(2, invalid)], 'attempt')).toBeUndefined()
        const projected = projectExecutionGraph([progress(1), progress(2, invalid)], 'attempt')!
        expect(projected.checkpoints.map(c => c.checkpoint.ref)).toEqual(['checkpoint:1'])
      })
    }
  }
  it.each([{ bad: true }, ['bad'], 42, null, ''].map(diagnostic => ({ diagnostic })))('rejects malformed optional recomputation diagnostics: %j', ({ diagnostic }) => {
    const invalid = graph(); invalid.results = [{ ...result(), recompute_reason: { kind: 'discrepancy', refs: ['source:one'], diagnostic } }]
    expect(projectExecutionGraph([progress(2, invalid)], 'attempt')).toBeUndefined()
    expect(projectExecutionGraph([progress(1), progress(2, invalid)], 'attempt')!.checkpoints).toHaveLength(1)
  })
  it.each([{ bad: true }, ['source_changed'], 42, null, 'unknown_reason'].map(kind => ({ kind })))('rejects unpublished recomputation kinds: %j', ({ kind }) => {
    const invalid = graph(); invalid.results = [{ ...result(), recompute_reason: { kind, refs: [] } }]
    expect(projectExecutionGraph([progress(2, invalid)], 'attempt')).toBeUndefined()
    expect(projectExecutionGraph([progress(1), progress(2, invalid)], 'attempt')!.checkpoints).toHaveLength(1)
  })
  it.each(['source_changed', 'method_changed', 'missing_result', 'discrepancy'])('accepts published recomputation kind %s without an optional diagnostic', kind => {
    const valid = graph(); valid.results = [{ ...result(), recompute_reason: { kind, refs: [] } }]
    expect(projectExecutionGraph([progress(1, valid)], 'attempt')!.current.results[0].recompute_reason).toEqual({ kind, refs: [] })
  })
})

describe('phase-specific graph action leases', () => {
  const activeGraph = (phase: string) => {
    const value = graph([node('A', [], phase)])
    if (['recorded', 'assessing'].includes(phase)) {
      value.nodes[0].assess_action_id = 'assess:A' as never
      value.actions = [{ ...action('A'), id: 'assess:A', kind: 'assess' }]
    }
    return value
  }
  for (const phase of ['executing', 'executed', 'recorded', 'assessing']) {
    it(`requires the current ${phase} lease instead of trusting node action IDs`, () => {
      const invalid = activeGraph(phase); invalid.actions = []
      expect(projectExecutionGraph([progress(2, invalid)], 'attempt')).toBeUndefined()
      expect(projectExecutionGraph([progress(1), progress(2, invalid)], 'attempt')!.checkpoints).toHaveLength(1)
    })
    it(`requires the ${phase} lease input bindings to match the node`, () => {
      const invalid = activeGraph(phase)
      Object.assign(invalid.actions[0], { input_bindings: [{ input_name: 'data', producer_step_id: 'A', result_ref: 'result:old', slot: 'answer' }] })
      expect(projectExecutionGraph([progress(2, invalid)], 'attempt')).toBeUndefined()
    })
    it(`admits the exact ${phase} lease`, () => {
      expect(projectExecutionGraph([progress(1, activeGraph(phase))], 'attempt')!.current.nodes[0].phase).toBe(phase)
    })
  }
  it.each(['success', 'limited', 'failure'])('keeps terminal %s snapshots with historical action refs and no current lease', phase => {
    const terminal = graph([node('A', [], phase)]); terminal.actions = []
    expect(projectExecutionGraph([progress(1, terminal)], 'attempt')!.current.nodes[0].phase).toBe(phase)
  })
  it.each(['envelope', 'transition'])('does not treat a historical node action ref as an admitted %s action', location => {
    const terminal = graph([node('A', [], 'success')]); terminal.actions = []
    const extras = location === 'envelope' ? { action_id: 'action:A' } : { events: [{ kind: 'node_settled', step_id: 'A', action_id: 'action:A' }] }
    expect(projectExecutionGraph([progress(1, terminal, extras)], 'attempt')).toBeUndefined()
  })
  it('retains earlier leases and late native events after terminal nodes leave the current action list', () => {
    const terminal = graph([node('A', [], 'success'), node('B', [], 'executing')]); terminal.actions = [action('B')]
    terminal.graph_ref = 'graph:2'; terminal.graph_revision = 2
    const projected = projectExecutionGraph([progress(1), progress(2, terminal, { action_id: 'action:A', events: [{ kind: 'node_settled', step_id: 'A', action_id: 'action:A', actual_summary: 'Original A' }] }), frame(3, 'enterprise_graph_child_tool', 'A', { activity: 'end', tool_call_id: 'call:A:late', tool_name: 'read' })], 'attempt')!
    expect(projected.current.graph_ref).toBe('graph:2')
    expect(projected.executions.find(e => e.action.id === 'action:A')).toMatchObject({ resultSummary: 'Original A', tools: [{ id: 'call:A:late', status: 'completed' }] })
  })
})

describe('scalar graph enums', () => {
  const fields: { name: string; token: string; nullable?: boolean; set: (g: ReturnType<typeof graph>, value: unknown) => void }[] = [
    { name: 'output mode', token: 'text', set: (g, value) => { Object.assign(g, { output_mode: value }) } },
    { name: 'node mode', token: 'execute', set: (g, value) => { Object.assign(g.nodes[0], { mode: value }) } },
    { name: 'node execution', token: 'delegated', set: (g, value) => { Object.assign(g.nodes[0], { execution: value }) } },
    { name: 'declared output kind', token: 'observation', set: (g, value) => { Object.assign(g.nodes[0].outputs[0], { kind: value }) } },
    { name: 'node phase', token: 'executing', set: (g, value) => { Object.assign(g.nodes[0], { phase: value }) } },
    { name: 'node applicability', token: 'current', set: (g, value) => { Object.assign(g.nodes[0], { applicability: value }) } },
    { name: 'node settlement', token: 'completed', nullable: true, set: (g, value) => { Object.assign(g.nodes[0], { settled_status: value }) } },
    { name: 'action kind', token: 'assess', set: (g, value) => {
      Object.assign(g.nodes[0], { phase: 'success', assess_action_id: 'assess:A' })
      Object.assign(g.actions[0], { id: 'assess:A', kind: value })
    } },
    { name: 'result kind', token: 'observation', set: (g, value) => { g.results = [{ ...result(), kind: value }] } },
    { name: 'recomputation kind', token: 'source_changed', set: (g, value) => { g.results = [{ ...result(), recompute_reason: { kind: value, refs: [] } }] } },
  ]
  for (const field of fields) {
    const invalid = [[field.token], { kind: field.token }, 42, ...(field.nullable ? [] : [null])]
    it.each(invalid.map(value => ({ value })))(`rejects non-string ${field.name}: %j before admitting a first or later snapshot`, ({ value }) => {
      const bad = graph(); field.set(bad, value)
      expect.soft(projectExecutionGraph([progress(2, bad)], 'attempt') === undefined).toBe(true)
      const retained = projectExecutionGraph([progress(1), progress(2, bad)], 'attempt')!
      expect(retained.checkpoints.map(c => c.checkpoint.ref)).toEqual(['checkpoint:1'])
    })
  }
  it.each(['executing', 'executed', 'recorded', 'assessing'])('rejects array phase [%s] with no lease and retains the prior checkpoint', phase => {
    const bad = graph(); bad.actions = []; Object.assign(bad.nodes[0], { phase: [phase] }); Object.assign(bad.nodes[1], { phase: 'success' })
    expect.soft(projectExecutionGraph([progress(2, bad)], 'attempt') === undefined).toBe(true)
    expect(projectExecutionGraph([progress(1), progress(2, bad)], 'attempt')!.checkpoints.map(c => c.checkpoint.ref)).toEqual(['checkpoint:1'])
  })
  it('keeps null settlement as the published unknown value', () => {
    expect(projectExecutionGraph([progress(1)], 'attempt')!.current.nodes[0].settled_status).toBeNull()
  })
  const malformedEnums = (token: string) => [[token], { kind: token }, null].map(value => ({ value }))
  it.each(malformedEnums('enterprise_graph_tool_binding'))('does not admit a coerced native frame type: %j', ({ value }) => {
    const projected = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_tool_binding', 'A', { type: value, tool_call_id: 'call:A', tool_name: 'read' }), event(3, { native_type: 'tool_execution_start', task_id: 'task', tool_call_id: 'call:A', tool_name: 'read' })], 'attempt')!
    expect(projected.executions[0].tools).toEqual([])
  })
  it.each(malformedEnums('start'))('does not admit a coerced child tool activity: %j', ({ value }) => {
    const projected = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_child_tool', 'A', { activity: value, tool_call_id: 'call:A', tool_name: 'read' })], 'attempt')!
    expect(projected.executions[0].tools).toEqual([])
  })
  it.each(malformedEnums('completed'))('does not admit a coerced child settlement status: %j', ({ value }) => {
    const projected = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_child_finished', 'A', { status: value })], 'attempt')!
    expect(projected.executions[0].nativeStatus).toBeUndefined()
    expect(projected.executions[0].finishedAt).toBeUndefined()
  })
  it.each(malformedEnums('tool_execution_start'))('does not admit a coerced generic native event type: %j', ({ value }) => {
    const projected = projectExecutionGraph([progress(1), frame(2, 'enterprise_graph_tool_binding', 'A', { tool_call_id: 'call:A', tool_name: 'read' }), event(3, { native_type: value, task_id: 'task', tool_call_id: 'call:A', tool_name: 'read' })], 'attempt')!
    expect(projected.executions[0].tools).toEqual([])
  })
  it.each(malformedEnums('graph_committed'))('does not convert malformed control event kinds into graph commits: %j', ({ value }) => {
    expect(projectExecutionGraph([progress(1, graph(), { events: [{ kind: value }] })], 'attempt')!.controlEvents).toEqual([])
  })
})
