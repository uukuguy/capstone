import { afterEach, describe, expect, it } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import ExecutionGraphProcess from './ExecutionGraphProcess'
import { projectExecutionGraph, type ExecutionGraph } from './executionGraph'
import type { EventEnvelope } from './threadProtocol'

afterEach(() => { cleanup(); localStorage.clear() })
function fixture(): ExecutionGraph {
  const owner = { thread_id: 'thread', work_id: 'work', research_id: 'research', goal_revision: 1 }
  const nodes = ['A', 'B', 'C', 'D'].map((id, index) => ({ id, purpose: `Original question ${id}`, questions: [`Why ${id}?`], checks: ['Check source'], depends_on: index === 2 ? ['A'] : index === 3 ? ['A', 'B'] : [], expected_outputs: ['Finding'], mode: 'execute', execution: 'delegated', instruction: 'Use selected evidence', outputs: [{ slot: 'finding', kind: 'observation', description: 'Finding' }], inputs: [], phase: ['success', 'executing', 'ready', 'pending'][index], applicability: 'current', execution_revision: 1, execute_action_id: index < 2 ? `action:${id}` : null, assess_action_id: null, input_bindings: [], output_bindings: index === 0 ? [{ slot: 'finding', result_ref: 'result:A:1' }] : [], blocked_by: index === 3 ? ['B'] : [], wait_reason: index === 3 ? 'dependencies' : null, settled_status: index === 0 ? 'completed' : null }))
  const graph = { schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:one', graph_revision: 1, goal: 'Actual graph', output_mode: 'text', model_revision_reason: null, nodes, actions: [{ id: 'action:B', owner, attempt_id: 'attempt', step_id: 'B', kind: 'execute', execution_revision: 1, graph_ref: 'graph:one', graph_revision: 1, input_bindings: [] }], results: [{ schema: 'capstone-task-result/1', result_ref: 'result:A:1', producer: { step_id: 'A', action_id: 'action:A', execution_revision: 1, attempt_id: 'attempt' }, slot: 'finding', kind: 'observation', summary: '## Finding\n\n**Confirmed** ' + 'Measured values. '.repeat(40) + '\n\n## Method\n\n- Use `source_id`\n\n| Field | Value |\n| --- | --- |\n| Total | 12 |', scope: 'selected rows', consumed_results: ['result:older'], source_versions: [{ ref: 'source:one', revision: 'v1' }], method: { ref: 'method:one', revision: 'v2', environment_unavailable: 'not supplied' }, supersedes: ['result:A:0'], recompute_reason: { kind: 'source_changed', refs: ['source:one'], diagnostic: 'Source changed' } }] }
  return projectExecutionGraph([{ eventId: 'event', eventSeq: 1, eventType: 'runtime_event', eventVersion: 1, threadId: 'thread', runId: 'run', attemptId: 'attempt', occurredAt: '2026-10-21T00:00:00Z', visibility: 'public', payload: { research_graph: { type: 'enterprise_graph_progress', owner, attempt_id: 'attempt', task_id: 'task', checkpoint: { ref: 'checkpoint:one', revision: 1 }, graph, events: [] } } } as EventEnvelope], 'attempt')!
}

describe('actual graph process reader', () => {
  it('shows main-chain finalization after the task executors finish, with live request timing', () => {
    const value=fixture()
    value.current.nodes=value.current.nodes.slice(0,1)
    value.executions=[{action:{...value.executions[0].action,id:'action:A',step_id:'A'},node:value.current.nodes[0],tools:[],responses:[],nativeStatus:'completed',executionFinishedAt:'2026-10-21T00:00:10Z'}]
    value.parentPendingResponse={id:'main-live',startedAt:'2026-10-21T00:00:12Z'}
    const props={graph:value,storageKey:'main-tail',attemptPhase:'running',now:Date.parse('2026-10-21T00:00:15Z')}
    const view=render(<ExecutionGraphProcess {...props} />)
    expect(screen.queryByRole('region',{name:'任务收尾'})).toBeNull()
    expect(screen.getByText(/主链编排 · 接收结果并判断下一步/)).toBeVisible()
    view.rerender(<ExecutionGraphProcess {...props} overallTools={[{id:'goal-review',name:'pi · agent_research_assess',status:'running',startedAt:'2026-10-21T00:00:14Z'}]} />)
    const tail=screen.getByRole('region',{name:'任务收尾'})
    expect(within(tail).getByText('模型处理中')).toBeVisible()
    expect(within(tail).getByText('已用时 5.0s')).toBeVisible()
    fireEvent.click(within(tail).getByRole('button',{name:'展开步骤：任务收尾'}))
    expect(within(tail).getByRole('group',{name:'主链 · LLM 01'})).toHaveTextContent('3.0s')
    value.parentPendingResponse=undefined
    value.parentResponses=[{id:'main-done',startedAt:'2026-10-21T00:00:12Z',finishedAt:'2026-10-21T00:00:18Z',ms:6000,kind:'text'}]
    view.rerender(<ExecutionGraphProcess graph={value} storageKey="main-tail" attemptPhase="completed" />)
    expect(within(tail).getByText('总耗时 8.0s')).toBeVisible()
    expect(within(tail).queryByText('模型处理中')).toBeNull()
  })
  it('totals main and task model calls and deduplicates tool identities', () => {
    const value=fixture(), execution=value.executions[0]
    execution.responses=[{number:1,ms:1500,toolCallIds:['same-tool']}]
    execution.tools=[{id:'same-tool',name:'read',status:'completed',startedAt:'2026-10-21T00:00:01Z',durationMs:1000}]
    value.parentResponses=[{id:'main-response',kind:'tools',ms:2500,startedAt:'2026-10-21T00:00:00Z',finishedAt:'2026-10-21T00:00:01Z'}]
    render(<ExecutionGraphProcess graph={value} storageKey="totals" overallTools={execution.tools} attemptPhase="completed" />)
    const totals=screen.getByLabelText('本轮整体计量')
    expect(within(totals).getByText('LLM 总计 2次 / 4.0s')).toBeVisible()
    expect(within(totals).getByText('工具总计 1次 / 活动区间 1.0s')).toBeVisible()
  })
  it('opens the affected call trace and preserves a later manual collapse', () => {
    const value = fixture()
    value.executions[0].responses = [{ number: 1, ms: 1200, toolCallIds: ['missing'] }]
    value.executions[0].nativeStatus = 'completed'
    const view = render(<ExecutionGraphProcess graph={value} storageKey="trace-warning" attemptPhase="completed" />)
    const task = screen.getByRole('region', { name: 'Original question B' })
    fireEvent.click(within(task).getByRole('button', { name: '定位本任务的工具记录缺失' }))
    expect(within(task).getByRole('group', { name: 'LLM 调用 1' })).toBeVisible()
    fireEvent.click(within(task).getByRole('button', { name: '折叠步骤：Original question B' }))
    view.rerender(<ExecutionGraphProcess graph={value} storageKey="trace-warning" attemptPhase="completed" />)
    expect(within(task).getByRole('button', { name: '展开步骤：Original question B' })).toHaveAttribute('aria-expanded', 'false')
  })
  it('distinguishes tool execution from the observed record interval in tool details', () => {
    const value = fixture()
    value.executions[0].tools = [{ id: 'timed', name: 'bash', status: 'completed', durationMs: 71900, executionMs: 2700 }]
    render(<ExecutionGraphProcess graph={value} storageKey="native-timing" expandedResearch />)
    const b = screen.getByRole('region', { name: 'Original question B' })
    fireEvent.click(within(b).getByText('调用过程', { selector: 'summary' }))
    fireEvent.click(within(b).getByText('bash', { selector: 'strong' }))
    expect(within(b).getByText(/工具执行 2.7s · 记录区间 71.9s/)).toBeVisible()
  })
  it('reveals actual started steps progressively and retains future steps in an optional plan', () => {
    const value = fixture()
    const view = render(<ExecutionGraphProcess graph={value} storageKey="progressive" />)
    expect(screen.getByRole('region', { name: 'Original question A' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Original question C' })).toBeNull()
    value.current.nodes[2] = { ...value.current.nodes[2], execute_action_id: 'action:C', phase: 'executing' }
    view.rerender(<ExecutionGraphProcess graph={value} storageKey="progressive" />)
    expect(screen.getByRole('region', { name: 'Original question C' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Original question D' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    expect(screen.getByRole('region', { name: 'Original question D' })).toBeVisible()
  })
  it('updates a running tool interval without writing a fabricated completion duration', () => {
    const value = fixture(), execution = value.executions[0]
    execution.tools = [{ id: 'running', name: 'bash', status: 'running', startedAt: '2026-10-21T00:00:04Z' }]
    const view = render(<ExecutionGraphProcess graph={value} storageKey="running-tool" now={Date.parse('2026-10-21T00:00:06Z')} />)
    expect(screen.getByText('工具 1次 / 2.0s')).toBeVisible()
    view.rerender(<ExecutionGraphProcess graph={value} storageKey="running-tool" now={Date.parse('2026-10-21T00:00:07Z')} />)
    expect(screen.getByText('工具 1次 / 3.0s')).toBeVisible()
    expect(execution.tools[0].durationMs).toBeUndefined()
  })
  it('does not show blank timing counters for a step that never started', () => {
    render(<ExecutionGraphProcess graph={fixture()} storageKey="not-started" attemptPhase="completed" />)
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    const c = screen.getByRole('region', { name: 'Original question C' })
    expect(within(c).getByText('未执行')).toBeVisible()
    expect(within(c).queryByText('LLM —')).toBeNull()
    expect(within(c).queryByText('耗时 —')).toBeNull()
  })
  it('keeps result, task and execution as peer sections with technical instructions under diagnostics', () => {
    render(<ExecutionGraphProcess graph={fixture()} storageKey="hierarchy" expandedResearch />)
    const a = screen.getByRole('region', { name: 'Original question A' })
    const body = a.querySelector('.capstone-process-step-body')!
    const summaries=[...body.children].map(child => child.querySelector(':scope > summary'))
    expect(summaries.map(summary => summary?.textContent)).toEqual(['执行结果', '任务说明', '调用过程', '诊断信息'])
    for(const summary of summaries)expect(summary?.querySelector('svg[aria-hidden="true"]')).not.toBeNull()
    expect(within(a).getByText('Use selected evidence')).not.toBeVisible()
    expect(within(a).getByText('Why A?')).toBeVisible()
  })
  it('does not label matching dependencies as parallel without observed overlap', () => {
    render(<ExecutionGraphProcess graph={fixture()} storageKey="parallel" />)
    expect(screen.queryByRole('group', { name: /并行任务/ })).toBeNull()
    expect(screen.getByRole('region', { name: 'Original question A' })).toBeVisible()
    expect(screen.getByRole('region', { name: 'Original question B' })).toBeVisible()
  })
  it('keeps sequential independent tasks separate, including touching intervals', () => {
    const value = fixture(), b = value.executions[0]
    Object.assign(b, { executionStartedAt: '2026-10-21T00:00:04Z', executionFinishedAt: '2026-10-21T00:00:12Z' })
    value.executions.push({ ...b, node: value.current.nodes[0], action: { ...b.action, id: 'action:A', step_id: 'A' }, executionStartedAt: '2026-10-21T00:00:01Z', executionFinishedAt: '2026-10-21T00:00:04Z' })
    render(<ExecutionGraphProcess graph={value} storageKey="sequential" attemptPhase="completed" />)
    expect(screen.queryByRole('group', { name: /并行任务/ })).toBeNull()
  })
  it('groups observed overlapping branches without including their earlier preparation task', () => {
    const value = fixture(), b = value.executions[0], c = value.current.nodes[2]
    Object.assign(b, { executionStartedAt: '2026-10-21T00:00:05Z', executionFinishedAt: '2026-10-21T00:00:12Z' })
    value.executions.push({ ...b, node: value.current.nodes[0], action: { ...b.action, id: 'action:A', step_id: 'A' }, executionStartedAt: '2026-10-21T00:00:01Z', executionFinishedAt: '2026-10-21T00:00:04Z' })
    Object.assign(c, { depends_on: [], execute_action_id: 'action:C' })
    value.executions.push({ ...b, node: c, action: { ...b.action, id: 'action:C', step_id: 'C' }, executionStartedAt: '2026-10-21T00:00:06Z' })
    render(<ExecutionGraphProcess graph={value} storageKey="prepared-parallel" attemptPhase="completed" />)
    const group = screen.getByRole('group', { name: '并行任务 · 2 项' })
    expect(within(group).queryByRole('region', { name: 'Original question A' })).toBeNull()
    expect(within(group).getByRole('region', { name: 'Original question B' })).toBeVisible()
    expect(within(group).getByRole('region', { name: 'Original question C' })).toBeVisible()
  })
  it('measures a parallel group by elapsed wall time rather than summing child durations', () => {
    const value = fixture(), b = value.executions[0]
    Object.assign(b, { executionStartedAt: '2026-10-21T00:00:04Z', executionFinishedAt: '2026-10-21T00:00:12Z', executionIntervalMs: 8000 })
    b.tools = [{ id: 'parallel-one', name: 'read', status: 'completed', startedAt: '2026-10-21T00:00:04Z', finishedAt: '2026-10-21T00:00:06Z', durationMs: 2000 }]
    b.responses = [{ number: 1, ms: 7000 }]
    value.executions.push({ ...b, node: value.current.nodes[0], action: { ...b.action, id: 'action:A', step_id: 'A' }, executionStartedAt: '2026-10-21T00:00:01Z', executionFinishedAt: '2026-10-21T00:00:09Z' })
    value.executions[1].tools = [{ id: 'parallel-two', name: 'read', status: 'completed', startedAt: '2026-10-21T00:00:05Z', finishedAt: '2026-10-21T00:00:07Z', durationMs: 2000 }]
    value.executions[1].responses = [{ number: 1, ms: 6000 }]
    render(<ExecutionGraphProcess graph={value} storageKey="parallel-wall" attemptPhase="completed" />)
    expect(within(screen.getByRole('group', { name: '并行任务 · 2 项' })).getByText('总耗时 11.0s')).toBeVisible()
    expect(screen.queryByText('总耗时 16.0s')).toBeNull()
    const heading = screen.getByRole('group', { name: '并行任务 · 2 项' }).querySelector('.capstone-graph-parallel-heading')!
    expect(heading).toHaveTextContent('工具 2次 / 3.0s')
    expect(heading).toHaveTextContent('LLM 2次 / 13.0s')
  })
  it('shows concurrent live children only from open execution intervals and stops the live indicator at termination', () => {
    const value = fixture(), b = value.executions[0]
    Object.assign(b, { executionStartedAt: '2026-10-21T00:00:01Z' })
    value.executions.push({ ...b, node: value.current.nodes[0], action: { ...b.action, id: 'action:A', step_id: 'A' } })
    const { rerender } = render(<ExecutionGraphProcess graph={value} storageKey="parallel-live" now={Date.parse('2026-10-21T00:00:09Z')} />)
    expect(screen.getByText('正在同时执行 2 项')).toBeVisible()
    expect(screen.getByText('已用时 8.0s')).toBeVisible()
    rerender(<ExecutionGraphProcess graph={value} storageKey="parallel-live" attemptPhase="completed" />)
    expect(screen.queryByText('正在同时执行 2 项')).toBeNull()
    expect(screen.queryByRole('group', { name: /并行任务/ })).toBeNull()
  })
  it('shows a cancelled child as cancelled after the parent attempt ends', () => {
    const value = fixture()
    value.executions[0].nativeStatus = 'cancelled'
    render(<ExecutionGraphProcess graph={value} storageKey="cancelled-child" attemptPhase="completed" />)
    expect(screen.getByRole('region', { name: 'Original question B' }).querySelector('.capstone-graph-node-heading')?.textContent).toContain('已取消')
  })
  it('numbers simultaneous steps and keeps interruption explanation in step details', () => {
    const value = fixture()
    render(<ExecutionGraphProcess graph={value} storageKey="numbered" attemptPhase="cancelled" />)
    const b = screen.getByRole('region', { name: 'Original question B' })
    expect(b.querySelector('.capstone-graph-node-heading')?.textContent).toContain('02')
    expect(b.querySelector('.capstone-graph-node-heading')?.textContent).toContain('已取消')
    expect(b.querySelector('.capstone-graph-node-heading')?.textContent).not.toContain('最后步骤状态')
    expect(within(b).getByText(/最后步骤状态：执行中/)).not.toBeVisible()
    expect(screen.getByRole('region', { name: 'Original question A' }).querySelector('.capstone-step-number')).toHaveTextContent('01')
  })
  it('shows live execution elapsed time only while the attempt is running', () => {
    const value = fixture()
    value.executions[0].executionStartedAt = '2026-10-21T00:00:01Z'
    const { rerender } = render(<ExecutionGraphProcess graph={value} storageKey="live" now={Date.parse('2026-10-21T00:00:09Z')} />)
    expect(screen.getByText('8.0s')).toBeVisible()
    expect(screen.queryByText(/进行中/)).toBeNull()
    rerender(<ExecutionGraphProcess graph={value} storageKey="live" attemptPhase="cancelled" />)
    expect(screen.queryByText('8.0s')).toBeNull()
    expect(value.executions[0].executionIntervalMs).toBeUndefined()
  })
  it('updates observed parent LLM accounting before the current action settles', () => {
    const value = fixture(), execution = value.executions[0]
    value.current.nodes[1].execution = 'parent'
    Object.assign(execution, { executionStartedAt: '2026-10-21T00:00:01Z' })
    value.parentResponses = [{ id: 'live-response', startedAt: '2026-10-21T00:00:02Z', finishedAt: '2026-10-21T00:00:04Z', ms: 2000, kind: 'tools' }]
    render(<ExecutionGraphProcess graph={value} storageKey="live-parent" now={Date.parse('2026-10-21T00:00:08Z')} />)
    expect(within(screen.getByRole('region', { name: 'Original question B' })).getByText('LLM 1次 / 2.0s')).toBeVisible()
  })
  it('keeps parent LLM and step tool timings visible outside folded diagnostics', () => {
    const value = fixture(), execution = value.executions[0]
    value.parentResponses = [
      { id: 'r1', startedAt: '2026-10-21T00:00:02Z', finishedAt: '2026-10-21T00:00:04Z', ms: 2000, kind: 'tools' },
      { id: 'r2', startedAt: '2026-10-21T00:00:05Z', finishedAt: '2026-10-21T00:00:08Z', ms: 3000, kind: 'error' }]
    Object.assign(execution, { executionStartedAt: '2026-10-21T00:00:01Z', executionFinishedAt: '2026-10-21T00:00:09Z', executionIntervalMs: 8000 })
    execution.node.execution = 'parent'
    execution.tools = [{ id: 'one', name: 'read', status: 'completed', startedAt: '2026-10-21T00:00:04Z', finishedAt: '2026-10-21T00:00:05Z', durationMs: 1000 }]
    render(<ExecutionGraphProcess graph={value} storageKey="timing" />)
    expect(screen.getByText('本轮主流程 LLM 2次 / 5.0s')).toBeVisible()
    expect(screen.getByText('错误响应 1次 / 3.0s')).toBeVisible()
    const b = screen.getByRole('region', { name: 'Original question B' })
    expect(within(b).getByText('工具 1次 / 1.0s')).toBeVisible()
    expect(within(b).getByText('LLM 2次 / 5.0s')).toBeVisible()
    expect(within(b).getByText('8.0s')).toBeVisible()
    expect(b.querySelector('.capstone-graph-node-heading')?.textContent).toContain('工具 1次 / 1.0s')
    expect(within(b).getByText('父主流程共享模型，未提供按节点计量')).not.toBeVisible()
    expect(within(b).queryByText('执行耗时未知')).toBeNull()
    expect(screen.getByText('LLM 请求计时明细')).toBeVisible()
    expect(screen.getByText('请求 1 · 工具请求 · 2.0s')).not.toBeVisible()
  })
  it('keeps exact references inside user-opened diagnostics in the enlarged reader', () => {
    const value = fixture()
    Object.assign(value.current.nodes[0], { source_refs: ['source:raw:selected'], selected_source_versions: [{ ref: 'source:raw:selected', revision: 'v7' }] })
    Object.assign(value.current.nodes[0], { input_bindings: [{ input_name: 'prior', result_ref: 'result:A:0', slot: 'finding', producer_step_id: 'A' }] })
    render(<ExecutionGraphProcess graph={value} storageKey="private-diagnostics" expandedResearch />)
    const a = screen.getByRole('region', { name: 'Original question A' })
    expect(within(a).getByText('result:A:1')).not.toBeVisible()
    expect(within(a).getByText('source:raw:selected')).not.toBeVisible()
    for(const item of within(a).getAllByText('result:A:0')) expect(item).not.toBeVisible()
    expect(within(a).getByText('Use selected evidence')).not.toBeVisible()
    expect(within(a).getByText('Why A?')).toBeVisible()
    expect(within(a).getByText('Check source')).toBeVisible()
    fireEvent.click(within(a).getByText('诊断信息'))
    fireEvent.click(within(a).getByText('结果诊断'))
    expect(within(a).getByText('result:A:1')).toBeVisible()
  })
  it.each(['cancelled', 'failed', 'interrupted', 'completed'])('overlays attempt %s without rewriting the last model phase', phase => {
    const value = fixture()
    value.current.nodes[1].execution = 'parent'
    const { container } = render(<ExecutionGraphProcess graph={value} storageKey="terminal" attemptPhase={phase} />)
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    expect(within(screen.getByRole('region', { name: 'Original question B' })).getByText(/最后步骤状态：执行中/)).not.toBeVisible()
    expect(within(screen.getByRole('region', { name: 'Original question A' })).getByText('完成')).toBeVisible()
    expect(container.querySelectorAll('[data-attempt-interruption]')).toHaveLength(3)
    expect(within(screen.getByRole('region', { name: 'Original question B' })).getByText('父主流程共享模型，未提供按节点计量')).not.toBeVisible()
    expect(value.current.nodes[1].phase).toBe('executing')
  })
  it.each(['pending', 'ready', 'executing', 'executed', 'recorded', 'assessing', 'success', 'limited', 'failure'])('preserves %s under task cancellation', phase => {
    const value = fixture(); value.current.nodes[1].phase = phase
    render(<ExecutionGraphProcess graph={value} storageKey="retained-phase" attemptPhase="cancelled" />)
    const b = screen.getByRole('region', { name: 'Original question B' })
    expect(b.querySelector('[data-attempt-interruption]') !== null).toBe(!['success', 'limited', 'failure'].includes(phase))
    expect(b).toHaveAttribute('data-phase', phase)
  })
  it('shows task titles and natural prerequisites with exact parent execution intervals', () => {
    const value = fixture()
    value.current.nodes[1].execution = 'parent'
    value.executions[0].executionIntervalMs = 1234
    render(<ExecutionGraphProcess graph={value} storageKey="paths" />)
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：Original question C' }))
    fireEvent.click(within(screen.getByRole('region', { name: 'Original question C' })).getByText('调用过程', { selector: 'summary' }))
    expect(screen.getByText('完整计划 · 4 项')).toBeVisible()
    expect(screen.queryByText(/箭头表示声明依赖/)).toBeNull()
    expect(screen.getByRole('link', { name: '前置步骤：Original question C 依赖 Original question A' })).toHaveTextContent('Original question A')
    expect(screen.queryByRole('link', { name: '依赖 A → C' })).toBeNull()
    expect(screen.getByText('1.2s')).toBeVisible()
    expect(screen.queryByText('原生执行跨度 1.2s')).toBeNull()
  })
  it('shows assessment tool attribution in the current node without inventing a historical execution', () => {
    const value = fixture(), current = value.executions.find(item => item.action.step_id === 'B')!
    current.tools.push({ id: 'assess-call', name: 'agent_research_assess', status: 'completed', actionId: 'assess:B:exact', actionKind: 'assess' })
    render(<ExecutionGraphProcess graph={value} storageKey="assessment-tools" />)
    const b = screen.getByRole('region', { name: 'Original question B' })
    expect(within(b).getByText('agent_research_assess')).toBeInTheDocument()
    expect(within(b).getByText('assess:B:exact')).toBeInTheDocument()
    expect(within(b).getByText('评估行动')).toBeInTheDocument()
    expect(within(b).queryByText(/本步骤历史执行/)).not.toBeInTheDocument()
  })
  it('distinguishes bound raw versions, explicit no-source scope and missing historical scope', () => {
    const value = fixture()
    Object.assign(value.current.nodes[0], { source_refs: ['source:raw:selected'], selected_source_versions: [{ ref: 'source:raw:selected', revision: 'v7' }] })
    Object.assign(value.current.nodes[1], { source_refs: [], selected_source_versions: [] })
    Object.assign(value.executions[0].action, { source_refs: [], source_versions: [] })
    render(<ExecutionGraphProcess graph={value} storageKey="sources" expandedResearch />)
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    const a = screen.getByRole('region', { name: 'Original question A' })
    const b = screen.getByRole('region', { name: 'Original question B' })
    const d = screen.getByRole('region', { name: 'Original question D' })
    expect(within(a).getByText('source:raw:selected')).not.toBeVisible()
    for (const region of [a, b, d]) fireEvent.click(within(region).getByText('诊断信息'))
    fireEvent.click(within(a).getByText('绑定原始资料 · 1 项'))
    expect(within(a).getByText('source:raw:selected')).toBeVisible()
    expect(within(a).getByText('v7')).toBeVisible()
    expect(within(b).getByText('未绑定原始资料')).toBeVisible()
    expect(within(d).getByText('未记录原始资料范围')).toBeVisible()
  })
  it('shows actual branches and join links, original IDs, and the precise blocked node', () => {
    render(<ExecutionGraphProcess graph={fixture()} storageKey="graph" />)
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    const b = screen.getByRole('region', { name: 'Original question B' })
    const c = screen.getByRole('region', { name: 'Original question C' })
    const d = screen.getByRole('region', { name: 'Original question D' })
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：Original question C' }))
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：Original question D' }))
    for (const region of [c, d]) fireEvent.click(within(region).getByText('调用过程', { selector: 'summary' }))
    expect(within(b).getByText('执行中')).toBeVisible()
    expect(within(c).getByText('可执行')).toBeVisible()
    expect(within(d).getByText('等待 Original question B 完成')).toBeVisible()
    expect(screen.getByRole('link', { name: '前置步骤：Original question C 依赖 Original question A' })).toHaveAttribute('href', expect.stringContaining('A'))
    expect(screen.getByRole('link', { name: '前置步骤：Original question D 依赖 Original question B' })).toHaveAttribute('href', expect.stringContaining('B'))
    expect(screen.queryByText('准备')).toBeNull()
  })
  it('keeps result excerpts bounded and expands original Markdown and exact provenance on demand', () => {
    const { container } = render(<ExecutionGraphProcess graph={fixture()} storageKey="graph" />)
    expect(container.querySelector('.capstone-result-excerpt')!.textContent!.length).toBeLessThanOrEqual(181)
    expect(screen.queryByRole('table')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：Original question A' }))
    fireEvent.click(screen.getByRole('button', { name: '查看详细结果：Original question A · finding' }))
    expect(screen.getByRole('heading', { name: 'Method' })).toBeVisible()
    expect(screen.getByText('source_id').tagName).toBe('CODE')
    fireEvent.click(within(screen.getByRole('region', { name: 'Original question A' })).getByText('诊断信息', { selector: 'summary' }))
    fireEvent.click(screen.getByText('结果诊断'))
    expect(screen.getByText('method:one · v2')).toBeVisible()
    expect(screen.getByText('source:one · v1')).toBeVisible()
    expect(screen.getByText('result:older')).toBeVisible()
    expect(screen.getByText('result:A:0')).toBeVisible()
    expect(screen.getByText('Source changed')).toBeVisible()
  })
  it('labels unknown native return separately from model assessment and preserves old consumer refs', () => {
    const value = fixture()
    Object.assign(value.current.nodes[1], { phase: 'recorded', settled_status: 'unknown', input_bindings: [{ input_name: 'old', producer_step_id: 'A', slot: 'finding', result_ref: 'result:A:0' }] })
    value.executions[0].nativeStatus = 'unknown'
    render(<ExecutionGraphProcess graph={value} storageKey="graph" expandedResearch />)
    const b = screen.getByRole('region', { name: 'Original question B' })
    expect(within(b).getByText('待检查')).toBeVisible()
    expect(within(b).getByText('原生结束状态未知')).not.toBeVisible()
    expect(within(b).getByText('LLM —')).toBeVisible()
    fireEvent.click(within(b).getByText('诊断信息'))
    fireEvent.click(within(b).getByText('实际消费版本 · 1 项'))
    expect(within(b).getByText('result:A:0')).toBeVisible()
    expect(within(b).getByText(/保留实际消费版本/)).toBeVisible()
  })
  it('keeps prior execution input bindings visible after the node starts a new execution', () => {
    const value = fixture(), old = value.executions[0]
    old.node = structuredClone(old.node)
    old.node.input_bindings = [{ input_name: 'previous', producer_step_id: 'A', slot: 'finding', result_ref: 'result:A:0' }]
    value.current.nodes[1] = { ...value.current.nodes[1], execution_revision: 2, execute_action_id: 'action:B:2' }
    render(<ExecutionGraphProcess graph={value} storageKey="history" />)
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：Original question B' }))
    fireEvent.click(within(screen.getByRole('region', { name: 'Original question B' })).getByText('诊断信息'))
    fireEvent.click(screen.getByText('本步骤历史执行 · 1'))
    const b = screen.getByRole('region', { name: 'Original question B' })
    fireEvent.click(within(b).getByText('实际消费版本 · 1 项'))
    expect(within(b).getByText('result:A:0')).toBeVisible()
  })
})
