import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import CapstoneAssistantThread, { projectAssistantActivity, projectAssistantMessages } from './CapstoneAssistantThread'
import type { EventEnvelope, ResultProjection } from './threadProtocol'
import {parseProductRef} from './threadProducts'
import directExecutionLifecycle from './fixtures/directExecutionLifecycle.json'
import {parseEventEnvelope} from './threadProtocol'

afterEach(() => { cleanup(); localStorage.clear(); sessionStorage.clear() })

it('keeps catalog LLM choices per session and across sends while DR resets',async()=>{
  const catalog={schema:'capstone-thread-input-catalog/1' as const,revision:'r',context_id:'',selection_revision:'',objects:[],materials:[],resource_profiles:{},operations:[],llm_profiles:{default_profile_id:'local',profiles:[{id:'local',label:'Commercial',model:'flash',available:true},{id:'internal',label:'Intranet',model:'dsv4',available:true},{id:'custom',label:'Custom',model:'',available:false}]}}
  const onSend=vi.fn().mockResolvedValue(undefined)
  const props={events:[],disabled:false,isRunning:false,activity:[],onSend,onCancel:async()=>{},inputCatalog:catalog}
  const {rerender}=render(<CapstoneAssistantThread key="one" {...props} storageKey="llm-session-one"/>)
  expect((screen.getByRole('combobox',{name:'后端 LLM'}) as HTMLSelectElement).value).toBe('local')
  expect((screen.getByRole('option',{name:/Custom.*未配置/}) as HTMLOptionElement).disabled).toBe(true)
  fireEvent.change(screen.getByRole('combobox',{name:'后端 LLM'}),{target:{value:'internal'}})
  fireEvent.click(screen.getByRole('button',{name:'深度思考'}))
  fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'first'}})
  fireEvent.keyDown(screen.getByRole('textbox',{name:'Thread 指令'}),{key:'Enter',code:'Enter'})
  await waitFor(()=>expect(onSend).toHaveBeenCalledWith('automatic','first',expect.objectContaining({llm_profile_id:'internal',deep_research:true})))
  await waitFor(()=>expect(screen.getByRole('button',{name:'深度思考'}).getAttribute('aria-pressed')).toBe('false'))
  expect((screen.getByRole('combobox',{name:'后端 LLM'}) as HTMLSelectElement).value).toBe('internal')
  rerender(<CapstoneAssistantThread key="two" {...props} storageKey="llm-session-two"/>)
  expect((screen.getByRole('combobox',{name:'后端 LLM'}) as HTMLSelectElement).value).toBe('local')
  rerender(<CapstoneAssistantThread key="one-restored" {...props} storageKey="llm-session-one"/>)
  expect((screen.getByRole('combobox',{name:'后端 LLM'}) as HTMLSelectElement).value).toBe('internal')
  rerender(<CapstoneAssistantThread key="one-restored" {...props} inputCatalog={{...catalog,llm_profiles:{...catalog.llm_profiles,default_profile_id:'local'}}} storageKey="llm-session-one"/>)
  expect((screen.getByRole('combobox',{name:'后端 LLM'}) as HTMLSelectElement).value).toBe('internal')
})

const event = (eventType: string, eventSeq: number, payload: Record<string, unknown>, attemptId?: string, occurredAt = '2026-09-30T00:00:00Z'): EventEnvelope => ({
  eventId: `evt_${eventSeq}`, eventSeq, eventType, eventVersion: 1, threadId: 'thr_demo', runId: 'run_demo', attemptId,
  occurredAt, visibility: 'public', payload,
})

describe('CapstoneAssistantThread', () => {
  // Public boundaries from real Attempt attempt_83571febfda61ed7 (2026-10-25).
  it('keeps recorded host lifecycle stages out of direct answer and tool-chain focus', () => {
    const events=directExecutionLifecycle.map(parseEventEnvelope)
    const props={disabled:false,isRunning:false,activity:[],onSend:async()=>{},onCancel:async()=>{}}
    const {rerender}=render(<CapstoneAssistantThread {...props} events={events} />)
    fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
    let reader=within(screen.getByRole('dialog',{name:'执行过程'}))
    expect(reader.getByRole('region',{name:'思考状态'})).toBeTruthy()
    expect(reader.getAllByRole('group',{name:/LLM 调用/})).toHaveLength(1)
    expect(reader.queryByLabelText('任务步骤')).toBeNull()
    expect(reader.getByText('运行阶段与计时').closest('details')?.open).toBe(false)
    fireEvent.keyDown(screen.getByRole('dialog',{name:'执行过程'}),{key:'Escape'})
    const toolEvent=event('runtime_event',35,{native_type:'tool_execution_end',task_id:'task',tool_call_id:'read',tool_name:'read',task_step_id:'task-execution',activity:{operation:'Read a registered source'}},events[0].attemptId)
    rerender(<CapstoneAssistantThread {...props} events={[...events.slice(0,-1),toolEvent,events.at(-1)!]} />)
    fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
    reader=within(screen.getByRole('dialog',{name:'执行过程'}))
    expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
    expect(reader.queryByLabelText('任务步骤')).toBeNull()
    fireEvent.keyDown(screen.getByRole('dialog',{name:'执行过程'}),{key:'Escape'})
    const businessStep=event('runtime_event',36,{task_step:{id:'task-finalization-review',number:4,title:'核验与结果整理',status:'completed',result_summary:'Recorded business review'}},events[0].attemptId)
    rerender(<CapstoneAssistantThread {...props} events={[...events,businessStep]} />)
    fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
    reader=within(screen.getByRole('dialog',{name:'执行过程'}))
    expect(reader.getByLabelText('任务步骤')).toBeTruthy()
    expect(reader.getByText('Recorded business review')).toBeTruthy()
  })
  it('shows public thinking status before the first task or tool exists', () => {
    const events=[event('command_accepted',1,{kind:'send_auto',payload:{text:'分析资料'}},'startup'),event('attempt_started',2,{},'startup')]
    render(<CapstoneAssistantThread events={events} activity={projectAssistantActivity(events)} disabled={false} isRunning={true} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('Thinking…')
    expect(screen.queryByText('当前记录未提供公开思考摘要。')).toBeNull()
    expect(screen.queryByText('正在准备输入、规划和调度首个任务。')).toBeNull()
  })
  it('changes from measured thinking to visible tools to recorded tasks and keeps that focus on replay', () => {
    const start = [event('attempt_started', 1, {}, 'mixed'),
      event('runtime_action', 2, {phase:'started'}, 'mixed', '2026-09-30T00:00:01Z'),
      event('runtime_action', 3, {phase:'response_completed'}, 'mixed', '2026-09-30T00:00:03Z')]
    const props = {disabled:false,isRunning:true,activity:[],onSend:async()=>{},onCancel:async()=>{}}
    const {rerender,unmount} = render(<CapstoneAssistantThread {...props} events={start} />)
    expect(screen.getByRole('region',{name:'思考状态'}).textContent).toContain('Thinking…')
    expect(screen.getByRole('group',{name:'LLM 调用 1'}).textContent).toContain('2.0s')
    const toolEvents = [...start, event('runtime_event',4,{native_type:'tool_execution_start',task_id:'task',tool_call_id:'call',tool_name:'read',activity:{operation:'Read registered source'}},'mixed')]
    rerender(<CapstoneAssistantThread {...props} events={toolEvents} />)
    const tools = screen.getByRole('region',{name:'工具调用过程'})
    expect(within(tools).getByText('Read registered source')).toBeTruthy()
    expect(tools.closest('details')).toBeNull()
    expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
    const taskEvents = [...toolEvents,event('runtime_event',5,{task_step:{id:'check',number:1,title:'Compare source coverage',status:'running'}},'mixed')]
    rerender(<CapstoneAssistantThread {...props} events={taskEvents} />)
    expect(screen.getByText('Compare source coverage')).toBeTruthy()
    expect(screen.queryByRole('region',{name:'工具调用过程'})).toBeNull()
    unmount()
    render(<CapstoneAssistantThread {...props} isRunning={false} events={[...taskEvents,event('attempt_cancelled',6,{},'mixed')]} />)
    fireEvent.click(screen.getByRole('button',{name:'查看执行过程'}))
    expect(screen.getByText('Compare source coverage')).toBeTruthy()
    expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  })
  it('keeps direct-answer timing on refresh without rendering diagnostic reasoning as a public summary', () => {
    render(<CapstoneAssistantThread events={[event('attempt_started',1,{},'direct'),
      {...event('assistant_process_delta',2,{text:'PRIVATE_REASONING'},'direct'),visibility:'diagnostic'},
      event('runtime_action',3,{phase:'started'},'direct','2026-09-30T00:00:01Z'),
      event('runtime_action',4,{phase:'response_completed'},'direct','2026-09-30T00:00:03Z'),
      event('attempt_completed',5,{answer:'Hello'},'direct','2026-09-30T00:00:04Z')]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.getByText(/思考状态.*4.0s/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'查看执行过程'}))
    expect(screen.getByRole('group',{name:'LLM 调用 1'}).textContent).toContain('2.0s')
    expect(screen.queryByText('PRIVATE_REASONING')).toBeNull()
  })
  it.each([
    ['error','attempt_failed','错误响应'],
    ['aborted','attempt_cancelled','已中断'],
    [undefined,'attempt_failed','未完整记录'],
    [undefined,'attempt_interrupted','已中断'],
  ])('retains public model failure status on replay: %s / %s', (responseKind,terminal,label) => {
    const events=[event('attempt_started',1,{},'model-error'),
      event('runtime_action',2,{phase:'started'},'model-error','2026-09-30T00:00:01Z'),
      ...(responseKind?[event('runtime_action',3,{phase:'response_completed',response_kind:responseKind},'model-error','2026-09-30T00:00:03Z')]:[]),
      event(terminal,4,{},'model-error','2026-09-30T00:00:04Z')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
    const call=within(screen.getByRole('dialog',{name:'执行过程'})).getByRole('group',{name:'LLM 调用 1'})
    expect(within(call).getByText(label)).toBeTruthy()
    expect(within(call).queryByText('已返回')).toBeNull()
    expect(within(call).getByText(responseKind?'2.0s':'耗时 —')).toBeTruthy()
  })
  it('shows actual overlapping native calls and retained errors in the tool process reader', () => {
    const tool = (seq:number,call:string,type:string,seconds:number,is_error=false) => event('runtime_event',seq,
      {native_type:type,task_id:'task',tool_call_id:call,tool_name:call,is_error,activity:{operation:`Read ${call}`,output_excerpt:is_error?'Source unavailable':'Source read'}},
      'parallel',`2026-09-30T00:00:0${seconds}Z`)
    const events=[event('attempt_started',1,{},'parallel'),
      tool(2,'first','tool_execution_start',1),tool(3,'second','tool_execution_start',2),
      tool(4,'second','tool_execution_end',3,true),tool(5,'first','tool_execution_end',4),
      event('attempt_failed',6,{message:'A source is unavailable'},'parallel')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
    const tools=within(screen.getByRole('dialog',{name:'执行过程'})).getByRole('region',{name:'工具调用过程'})
    expect(within(tools).getAllByText('并行调用')).toHaveLength(2)
    expect(within(tools).getByText('失败')).toBeTruthy()
    expect(within(tools).getByText('Source unavailable',{selector:'.capstone-tool-failure-reason'})).toBeTruthy()
  })
  it('passes the trusted cancelled attempt phase to its retained graph reader', () => {
    const owner = { thread_id: 'thr_demo', work_id: 'work', research_id: 'research', goal_revision: 1 }
    const node = { id: 'actual-node', purpose: 'Retained parent', questions: [], checks: [], depends_on: [], expected_outputs: [], mode: 'execute', execution: 'parent', instruction: 'Use evidence', outputs: [], inputs: [], phase: 'ready', applicability: 'current', execution_revision: 1, execute_action_id: null, assess_action_id: null, blocked_by: [], wait_reason: null, input_bindings: [], output_bindings: [], settled_status: null }
    Object.assign(node, { source_refs: ['source:retained'], selected_source_versions: [{ ref: 'source:retained', revision: 'v1' }] })
    const graph = { schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:one', graph_revision: 1, goal: 'Inspect', output_mode: 'text', model_revision_reason: null, nodes: [node], actions: [], results: [] }
    render(<CapstoneAssistantThread events={[event('command_accepted', 1, { kind: 'send_auto', text: 'Inspect' }, 'graph'), event('attempt_started', 2, {}, 'graph'),
      event('runtime_event', 3, { research_graph: { type: 'enterprise_graph_progress', owner, attempt_id: 'graph', task_id: 'task', checkpoint: { ref: 'checkpoint:one', revision: 1 }, graph, events: [] } }, 'graph'),
      event('attempt_cancelled', 4, {}, 'graph')]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: '执行过程' })).getByRole('button', { name: '查看完整计划' }))
    expect(within(screen.getByRole('dialog', { name: '执行过程' })).getByText('任务已取消 · 最后步骤状态：可执行')).toBeTruthy()
    const source = within(screen.getByRole('dialog', { name: '执行过程' })).getByText('source:retained')
    expect(source.closest('details')!.open).toBe(false)
  })
  it.each(['input_name', 'producer_step_id'])('keeps the reader safe and uses legacy fallback for malformed %s', async field => {
    const owner = { thread_id: 'thr_demo', work_id: 'work', research_id: 'research', goal_revision: 1 }
    const node = { id: 'actual-node', purpose: 'Valid graph question', questions: [], checks: [], depends_on: [], expected_outputs: [], mode: 'execute', execution: 'parent', instruction: 'Use evidence', outputs: [], inputs: [], phase: 'ready', applicability: 'current', execution_revision: 1, execute_action_id: null, assess_action_id: null, blocked_by: [], wait_reason: null, input_bindings: [], output_bindings: [], settled_status: null }
    const graph = { schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:one', graph_revision: 1, goal: 'Inspect', output_mode: 'text', model_revision_reason: null, nodes: [node], actions: [], results: [] }
    const bad = structuredClone(graph)
    Object.assign(bad.nodes[0], { input_bindings: [{ result_ref: 'result:old', slot: 'answer', [field]: { bad: true } }] })
    const progress = (seq: number, value: typeof graph) => event('runtime_event', seq, { task_step: { id: 'legacy', number: 1, title: 'Safe legacy process', status: 'running' }, research_graph: { type: 'enterprise_graph_progress', owner, attempt_id: 'graph', task_id: 'task', checkpoint: { ref: `checkpoint:${seq}`, revision: seq }, graph: value, events: [] } }, 'graph')
    const start = [event('command_accepted', 1, { kind: 'send_auto', text: 'Inspect' }, 'graph'), event('attempt_started', 2, {}, 'graph')]
    const props = { disabled: false, isRunning: true, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={[...start, progress(3, bad)]} />)
    expect(screen.getByText('Safe legacy process')).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Valid graph question' })).toBeNull()
    rerender(<CapstoneAssistantThread {...props} events={[...start, progress(3, graph), progress(4, bad)]} />)
    fireEvent.click(document.querySelector('details.capstone-chat-activity > summary')!)
    await screen.findByRole('button', { name: '查看完整计划' })
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    expect(screen.getByRole('region', { name: 'Valid graph question' })).toBeTruthy()
    expect(screen.queryByText('Safe legacy process')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    fireEvent.click(within(screen.getByRole('dialog', { name: '执行过程' })).getByRole('button', { name: '查看完整计划' }))
    expect(within(screen.getByRole('dialog', { name: '执行过程' })).getByRole('region', { name: 'Valid graph question' })).toBeTruthy()
  })
  it('uses the admitted graph in the existing reader and leaves legacy projections out of graph records', async () => {
    const owner = { thread_id: 'thr_demo', work_id: 'work', research_id: 'research', goal_revision: 1 }
    const node = { id: 'actual-node', purpose: '模型原始研究问题', questions: ['为何发生？'], checks: [], depends_on: [], expected_outputs: ['解释'], mode: 'execute', execution: 'parent', instruction: '分析实际观察', outputs: [], inputs: [], phase: 'ready', applicability: 'current', execution_revision: 1, execute_action_id: null, assess_action_id: null, blocked_by: [], wait_reason: null, input_bindings: [], output_bindings: [], settled_status: null }
    const graph = { schema: 'capstone-enterprise-graph/2', graph_ref: 'graph:one', graph_revision: 1, goal: '分析原因', output_mode: 'text', model_revision_reason: null, nodes: [node], actions: [], results: [] }
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '分析原因' }, 'graph'), event('attempt_started', 2, {}, 'graph'), event('runtime_event', 3, { task_step: { id: 'legacy', number: 1, title: '旧单步骤准备', status: 'running' }, research_graph: { type: 'enterprise_graph_progress', owner, attempt_id: 'graph', task_id: 'task', checkpoint: { ref: 'checkpoint:one', revision: 1 }, graph, events: [{ kind: 'graph_committed', graph_ref: 'graph:one' }] } }, 'graph')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByLabelText('研究进展')).toBeTruthy()
    fireEvent.click(document.querySelector('details.capstone-chat-activity > summary')!)
    await screen.findByRole('button', { name: '查看完整计划' })
    fireEvent.click(screen.getByRole('button', { name: '查看完整计划' }))
    expect(screen.getByRole('region', { name: '模型原始研究问题' })).toBeTruthy()
    expect(screen.queryByText('旧单步骤准备')).toBeNull()
    const embeddedToggle = screen.getByRole('button', { name: '展开步骤：模型原始研究问题' })
    expect(embeddedToggle.getAttribute('aria-expanded')).toBe('false')
    const enlarge = screen.getByRole('button', { name: '放大阅读执行过程' }); enlarge.focus(); fireEvent.click(enlarge)
    const reader = screen.getByRole('dialog', { name: '执行过程' })
    fireEvent.click(within(reader).getByRole('button', { name: '查看完整计划' }))
    expect(within(reader).getByText('为何发生？')).toBeTruthy()
    expect(within(reader).getByText(/模型提交执行图/)).toBeTruthy()
    fireEvent.click(within(reader).getByRole('button', { name: '折叠步骤：模型原始研究问题' }))
    fireEvent.keyDown(reader, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(enlarge)
    expect(embeddedToggle.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(enlarge)
    fireEvent.click(within(screen.getByRole('dialog', { name: '执行过程' })).getByRole('button', { name: '查看完整计划' }))
    expect(within(screen.getByRole('dialog', { name: '执行过程' })).getByRole('button', { name: '展开步骤：模型原始研究问题' }).getAttribute('aria-expanded')).toBe('false')
  })
  it.each([false,true])('shows typed capacity values and phase without exposing raw exceptions, admitted partial=%s',partial=>{
    const capacity={code:'capacity_exceeded',dimension:'artifact_file_bytes',actual:8193,limit:8192,unit:'bytes',phase:'collect_artifacts',retryable:false}
    render(<CapstoneAssistantThread events={[
      event('assistant_text_delta',1,{text:'已经保存的分析。'},'bounded'),
      event('attempt_failed',2,{error_code:'native_capacity_exceeded',message:'RAW_EXCEPTION private/path secret',failure:{code:'native_capacity_exceeded',phase:'native_execution',capacity},...(partial?{answer:'已经保存的分析。',outcome:{status:'partial'}}:{})},'bounded'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.getByText('已经保存的分析。')).toBeTruthy()
    const notice=screen.getByText('执行超过容量限制').closest('.capstone-system-notice')!
    expect(notice.textContent).toContain('实际：8193 字节')
    expect(notice.textContent).toContain('上限：8192 字节')
    expect(notice.textContent).toContain('发生位置：collect_artifacts')
    expect(screen.queryByText(/RAW_EXCEPTION/)).toBeNull()
  })
  it('keeps malformed capacity records safe without inventing quantities or showing an exception',()=>{
    render(<CapstoneAssistantThread events={[event('attempt_failed',1,{error_code:'native_capacity_exceeded',error:'RAW_EXCEPTION credentials',failure:{code:'native_capacity_exceeded',phase:'native_execution',capacity:{actual:99}}},'bounded')]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.getByText(/当前记录未提供可核对的实际值与上限/)).toBeTruthy()
    expect(screen.queryByText(/RAW_EXCEPTION/)).toBeNull()
  })
  it('renders native work records and tools inside the shared runtime steps', () => {
    const step={id:'pi-task.runtime-1',number:1,title:'检查资料覆盖和缺失',status:'completed'}
    render(<CapstoneAssistantThread events={[
      event('runtime_action',1,{task_step:step},'native'),
      event('runtime_event',2,{task_id:'pi-task',native_type:'tool_execution_start',tool_name:'bash',tool_call_id:'read',task_step_id:step.id,activity:{operation:'读取上传资料'}},'native'),
      event('runtime_event',3,{task_id:'pi-task',native_type:'tool_execution_end',tool_name:'bash',tool_call_id:'read',is_error:false,task_step_id:step.id},'native'),
      event('runtime_event',4,{task_id:'pi-task',native_type:'tool_execution_end',tool_name:'agent_task_progress',tool_call_id:'note',is_error:false,task_step_id:step.id,runtime_step_tracking:true,task_progress:{kind:'observation',text:'两列存在缺失，按实际覆盖统计。',refs:[]}},'native'),
      event('attempt_completed',5,{answer:'分析完成',task_steps:[step]},'native'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    fireEvent.click(screen.getByRole('button',{name:'查看执行过程'}))
    const title=screen.getByText('检查资料覆盖和缺失')
    const section=title.closest('details')!
    expect(within(section).getByText('两列存在缺失，按实际覆盖统计。')).toBeTruthy()
    expect(within(section).getByText('读取上传资料')).toBeTruthy()
  })
  it('opens live process research details in a reader without changing embedded folds and restores focus with Escape', () => {
    const step = { id: 'readable', number: 1, title: '核查来源差异', status: 'running', questions: ['为何有差异？'], result_summary: '已确认一项差异' }
    const props = { disabled: false, isRunning: true, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '核查来源' }, 'reader'), event('attempt_started', 2, {}, 'reader'), event('runtime_event', 3, { task_step: step }, 'reader')]
    const { rerender, container } = render(<CapstoneAssistantThread {...props} events={events} />)
    const trigger = screen.getByRole('button', { name: '放大阅读执行过程' })
    const embeddedTools = container.querySelector<HTMLDetailsElement>('.capstone-business-step')!
    fireEvent.click(embeddedTools.querySelector('summary')!)
    const embeddedViewport = container.querySelector<HTMLElement>('.capstone-chat-activity-preview')!
    embeddedViewport.scrollTop = 37
    trigger.focus()
    expect(screen.queryByText('为何有差异？')).toBeNull()
    fireEvent.click(trigger)
    const reader = screen.getByRole('dialog', { name: '执行过程' })
    expect(within(reader).getByText('为何有差异？')).toBeTruthy()
    expect(within(reader).getByText('已确认一项差异')).toBeTruthy()
    expect(reader.querySelector<HTMLDetailsElement>('.capstone-business-step')!.open).toBe(false)
    rerender(<CapstoneAssistantThread {...props} events={[...events, event('runtime_event', 4, { task_step: { id: 'next', number: 2, title: '追加核查', status: 'partial', result_summary: '还有缺口' } }, 'reader')]} />)
    expect(within(reader).getAllByText('追加核查').length).toBeGreaterThan(0)
    fireEvent.keyDown(reader, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(trigger)
    expect(screen.queryByText('为何有差异？')).toBeNull()
    expect(container.querySelector<HTMLDetailsElement>('.capstone-business-step')!.open).toBe(true)
    expect(embeddedViewport.scrollTop).toBe(37)
  })
  it('shows actual branch results under their parent objective and keeps transition errors visible', () => {
    const step = { id: 'native-objective', number: 1, title: '解释异常差异', status: 'partial', questions: ['差异是否由缺数造成？'], expected_outputs: ['差异解释'], result_summary: '缺数解释不足', next_action_reason: '追加核查检修窗口' }
    const branch = { subordinate: true, parent_tool_call_id: 'delegate_one', child_id: 'check', title: '独立核对缺数', questions: ['缺数分布是否一致？'], expected_outputs: ['缺数对照'], owner: { thread_id: 'thr_demo' }, attempt_id: 'branches', parent_action_id: 'action_one', parent_step_id: step.id, checkpoint: { ref: 'checkpoint_one', revision: 1 } }
    const events = [event('runtime_event', 1, { task_step: step }, 'branches'),
      event('runtime_event', 2, { research_branch: { ...branch, type: 'delegation_child_started' } }, 'branches'),
      event('runtime_event', 3, { research_branch: { ...branch, type: 'delegation_child_tool', activity: 'tool_execution_end', tool_name: 'read', tool_call_id: 'read_one', is_error: false } }, 'branches'),
      event('runtime_event', 4, { research_branch: { ...branch, type: 'delegation_child_finished', status: 'completed', result_summary: '已完成缺数对照，仍需父任务综合' } }, 'branches'),
      event('runtime_event', 5, { task_step_error: 'Step transition was not applied; the existing step was retained.' }, 'branches'),
      event('attempt_failed', 6, { error_code: 'research_cycle_no_progress' }, 'branches')]
    const { container } = render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByRole('status').textContent).toContain('步骤未推进')
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    const objective = screen.getByText('解释异常差异').closest('.capstone-business-step-record')!
    expect(within(objective as HTMLElement).getAllByText('缺数解释不足').length).toBeGreaterThan(0)
    fireEvent.click(within(objective as HTMLElement).getByRole('button', { name: /展开步骤/ }))
    fireEvent.click(within(objective as HTMLElement).getByRole('button', { name: '下一步理由' }))
    expect(within(objective as HTMLElement).getByText('追加核查检修窗口')).toBeTruthy()
    expect(within(objective as HTMLElement).getByRole('region', { name: '子分支：独立核对缺数' })).toBeTruthy()
    expect(screen.getByText(/子执行完成，待综合评估/)).toBeTruthy()
    expect(screen.getByText('已完成缺数对照，仍需父任务综合')).toBeTruthy()
    expect(container.querySelector<HTMLDetailsElement>('.capstone-research-branch details')!.open).toBe(false)
    expect(container.querySelector<HTMLDetailsElement>('.capstone-business-step')!.open).toBe(false)
  })
  it('does not treat an empty business-object projection as missing uploaded files', () => {
    const events=[event('command_accepted',1,{kind:'send_auto',text:'分析上传资料'},'attempt_one'),
      event('turn_plan_created',2,{accepted_context:{objects:[],materials:[],full_model_tables:false}},'attempt_one'),
      event('attempt_completed',3,{answer:'报告已保存'},'attempt_one')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.queryByText('未提供完整网络表或文件资料。')).toBeNull()
    expect(screen.queryByText('本轮业务对象 · 0 个对象')).toBeNull()
  })
  it('keeps real business objects in the process reader auxiliary area only', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '检查模型' }, 'objects'),
      event('turn_plan_created', 2, { accepted_context: { objects: [{ object_id: 'model_one', display_name: '真实模型', version: 'v2' }] } }, 'objects'),
      event('attempt_completed', 3, { answer: '检查完成' }, 'objects'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.queryByText('本轮业务对象 · 1 个对象')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    expect(within(screen.getByRole('dialog')).getByText('本轮业务对象 · 1 个对象')).toBeTruthy()
    expect(screen.getByText('真实模型 · v2')).toBeTruthy()
  })
  it('folds unassigned tool details in the reader while keeping their failure summary visible', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_started', 1, {}, 'unassigned'),
      event('runtime_event', 2, { task_step: { id: 'known', number: 1, title: '已记录研究步骤', status: 'failed' } }, 'unassigned'),
      event('tool_started', 3, { tool_call_id: 'call_one', tool_name: 'grid_context_get' }, 'unassigned'),
      event('tool_completed', 4, { tool_call_id: 'call_one', ok: false, error: { message: '没有可用模型' } }, 'unassigned'),
      event('attempt_failed', 5, { error_code: 'tool_failed' }, 'unassigned'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    const reader = screen.getByRole('dialog')
    const tools = reader.querySelector<HTMLDetailsElement>('.capstone-unassigned-tool')!
    expect(tools.open).toBe(false)
    expect(within(reader).getByText('读取模型上下文：调用失败')).toBeTruthy()
    expect(within(reader).getByText('读取模型上下文：调用失败').closest('.capstone-unassigned-tool')).toBeNull()
  })
  it('hides protected configuration in older native output receipts', () => {
    const items=projectAssistantActivity([event('runtime_event',1,{
      task_id:'pi_one',native_type:'tool_execution_end',tool_name:'bash',tool_call_id:'one',
      activity:{output_excerpt:'{"apiKey":"private-value","models":["demo"]}'},
    },'attempt_one')])
    expect(items[0].outputExcerpt).toBe('输出包含受保护配置或凭据信息，已隐藏。')
    expect(JSON.stringify(items)).not.toContain('private-value')
  })
  it('keeps native operation and output bound to the same call across receipts', () => {
    const events = [
      event('runtime_event', 1, {task_id:'pi_one',native_type:'tool_execution_start',tool_name:'bash',tool_call_id:'one',activity:{operation:'python report.py'}}, 'attempt_one'),
      event('runtime_event', 2, {task_id:'pi_one',native_type:'tool_execution_end',tool_name:'bash',tool_call_id:'one',is_error:true,activity:{output_excerpt:'File not found: input.csv'}}, 'attempt_one'),
      event('runtime_event', 3, {task_id:'pi_one',native_type:'tool_execution_start',tool_name:'bash',tool_call_id:'two'}, 'attempt_one'),
    ]
    const projected=projectAssistantActivity(events)
    expect(projected[0]).toMatchObject({operation:'python report.py',outputExcerpt:'File not found: input.csv',status:'failed',failure:{summary:'File not found: input.csv'}})
    expect(projected[1].operation).toBeUndefined()
    expect(projected[1].outputExcerpt).toBeUndefined()
  })
  it('does not claim zero calls when restored history has no public tool records',()=>{
    const events=[event('attempt_started',1,{},'legacy_native'),event('attempt_completed',3,{answer:'文件已保存',task_steps:[{id:'prepare',number:1,title:'准备',status:'completed'}]},'legacy_native')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}}/>)
    expect(screen.getByText(/工具调用数未记录/)).toBeTruthy()
    expect(screen.getByTitle('当前记录未提供可核对的工具调用数量，可查看执行过程。')).toBeTruthy()
    expect(screen.queryByText(/0 次工具调用/)).toBeNull()
  })
  it('keeps an exact product reference in the existing draft until accepted or explicitly removed',async()=>{
    const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_demo',product_id:'delivery_one',origin:'task_delivery',scope:'task',event_seq:12,revision:2,digest:'a'.repeat(64),work_id:'old_work',attempt_id:'old_attempt',producer_attempt_id:null})
    const selection={ref,purpose:'historical-context' as const}
    const entry={ref,title:'季度分析.csv',media_type:'text/csv',byte_size:10,source_status:'completed',created_at:'2026-10-17T00:00:00Z',download_url:null,source:{},dependencies:[],presentation:{kind:'task_delivery' as const},capabilities:{read:true as const,select:true},selection_unavailable_reason:null,historical_only:true as const}
    const reader=vi.fn().mockResolvedValue({entry,bytes:null,projection:null,record:null}),send=vi.fn().mockResolvedValue(undefined)
    const base={events:[],disabled:false,isRunning:false,activity:[],onSend:send,onCancel:async()=>{},productReferenceReader:reader,storageKey:'product-reference-composer'}
    const view=render(<CapstoneAssistantThread {...base} requestedProductReference={{selection,nonce:1}}/>)
    await screen.findByText('季度分析.csv · v2')
    fireEvent.change(screen.getByRole('textbox',{name:'Thread 指令'}),{target:{value:'用此版本继续分析'}})
    fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
    await waitFor(()=>expect(send).toHaveBeenCalledWith('automatic','用此版本继续分析',expect.objectContaining({context_product_refs:[selection]})))
    await waitFor(()=>expect(screen.queryByRole('button',{name:'移除成果引用：季度分析.csv'})).toBeNull())
    view.rerender(<CapstoneAssistantThread {...base} requestedProductReference={{selection,nonce:2}}/>)
    fireEvent.click(await screen.findByRole('button',{name:'移除成果引用：季度分析.csv'}))
    expect(screen.queryByText('季度分析.csv · v2')).toBeNull()
    view.unmount();sessionStorage.removeItem('product-reference-composer.input');sessionStorage.removeItem('product-reference-composer.draft')
  })
  it('restores genuine native observations without counting missing identities or inventing task steps',()=>{
    // Saved production receipts carry task_id inside reference, not in the outer payload.
    const observation=(seq:number,call:string)=>event('runtime_event',seq,{external_reference_kind:'sources',reference:{kind:'native_tool_observation',task_id:'pi_saved',parent_attempt_id:'native_attempt',metadata:{tool_name:'bash',tool_call_id:call,output_sha256:'a'.repeat(64)}}},'native_attempt')
    const events=[event('command_accepted',1,{kind:'send_auto',text:'生成文件'},'native_attempt'),
      event('runtime_event',2,{task_id:'pi_saved',native_type:'tool_execution_start'},'native_attempt'),
      observation(3,'call_first'),observation(4,'call_second'),observation(5,'call_second'),
      event('attempt_completed',6,{answer:'文件已保存'},'native_attempt')]
    const activities=projectAssistantActivity(events)
    expect(activities).toHaveLength(2)
    expect(activities.map(item=>[item.label,item.source,item.status])).toEqual([['bash','pi · bash','completed'],['bash','pi · bash','completed']])
    const messages=projectAssistantMessages(events)
    expect(messages.at(-1)?.metadata?.custom?.activities).toEqual(activities)
    expect(messages.at(-1)?.metadata?.custom?.taskSteps).toEqual([])
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={activities} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.getByText(/2 次工具调用/)).toBeTruthy()
  })
  it('merges native live events and final observations by task and call identity, retaining true failures',()=>{
    const native=(seq:number,nativeType:string,payload:Record<string,unknown>={})=>event('runtime_event',seq,{task_id:'pi_live',native_type:nativeType,tool_name:'read',tool_call_id:'call_live',...payload},'native_attempt',`2026-10-17T13:00:0${seq}Z`)
    const started=native(1,'tool_execution_start')
    expect(projectAssistantActivity([started])[0]).toMatchObject({label:'read',status:'running',startedAt:started.occurredAt})
    const ended=native(2,'tool_execution_end',{is_error:true})
    const observation=event('runtime_event',3,{task_id:'pi_live',external_reference_kind:'sources',reference:{kind:'native_tool_observation',task_id:'pi_live',parent_attempt_id:'native_attempt',metadata:{tool_name:'read',tool_call_id:'call_live'}}},'native_attempt')
    const retry=native(4,'tool_execution_start',{tool_call_id:'call_retry'})
    expect(projectAssistantActivity([started,ended,observation,retry])).toMatchObject([{label:'read',status:'failed',finishedAt:ended.occurredAt,durationMs:1000},{label:'read',status:'running'}])
    expect(projectAssistantActivity([{...observation,payload:{...observation.payload,reference:{kind:'native_tool_observation',task_id:'pi_live',parent_attempt_id:'other_attempt',metadata:{tool_name:'read',tool_call_id:'call_live'}}}}])).toEqual([])
  })
  it('shows a persisted instruction file only beneath its owning answer',()=>{
    const digest='a'.repeat(64),artifactId=`file-${'b'.repeat(16)}-${digest}`
    const artifact={schema:'capstone-process-artifact/1',scope:'instruction',thread_id:'thr_demo',run_id:'run_demo',turn_id:'turn_one',attempt_id:'one',work_id:null,task_snapshot_id:null,goal_revision:null,task_id:'native_one',artifact_id:artifactId,executor_identity_sha256:'c'.repeat(64),source_status:'completed',file_name:'已保存说明.md',media_type:'text/markdown',sha256:digest,size_bytes:12,download_url:`/api/v1/threads/thr_demo/attempts/one/artifacts/${artifactId}`}
    const open=vi.fn()
    render(<CapstoneAssistantThread events={[{...event('native_artifact_published',1,{artifact},'one'),turnId:'turn_one'},event('attempt_completed',2,{answer:'附有文件的回答'},'one'),event('attempt_completed',3,{answer:'普通回答'},'two')]} onOpenNativeArtifact={open} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    const files=screen.getAllByRole('button',{name:'打开指令文件：已保存说明.md'})
    expect(files).toHaveLength(1)
    expect(files[0].closest('.capstone-chat-message')?.textContent).toContain('附有文件的回答')
    fireEvent.click(files[0])
    expect(open).toHaveBeenCalledWith(artifact)
  })
  it('keeps intermediate results available for inspection without final-product links', () => {
    const result: ResultProjection = {resultId:'r',resultRef:'result:r',evidenceRefs:[],threadId:'thr_demo',runId:'run_demo',turnId:'turn_one',attemptId:'one',modelContextId:'ctx',modelId:'ieee39',modelRevision:'7',source:{capabilityId:'powerflow.ac',domainPackId:'grid',implementationFamily:'pandapower'},status:'completed',summary:[{metricId:'loss',label:'有功损耗',value:1}],tables:[],elementRefs:[]}
    const open = vi.fn()
    result.presentation = {collectionId:'analysis',collectionTitle:'电网分析结果',groupId:'state_1',groupTitle:'运行状态 1',purpose:'task_output'}
    render(<CapstoneAssistantThread events={[event('attempt_completed',1,{answer:'计算说明'},'one'),event('attempt_completed',2,{answer:'普通说明'},'two')]} resultProjections={[result]} onOpenResultProduct={vi.fn()} onOpenTaskResults={open} disabled={false} isRunning={false} activity={[]} onSend={async()=>{}} onCancel={async()=>{}} />)
    expect(screen.queryByRole('button', {name:'打开计算结果：有功损耗'})).toBeNull()
    const conclusions = screen.getAllByRole('button', {name:'打开电网分析结果'})
    expect(conclusions).toHaveLength(1)
    fireEvent.click(conclusions[0])
    expect(open).toHaveBeenCalledWith(expect.objectContaining({attemptId:'one',title:'电网分析结果',results:[result]}))
    const buttons = screen.getAllByRole('button', {name:'查看计算结果'})
    expect(buttons).toHaveLength(1)
    fireEvent.click(buttons[0])
    expect(screen.getByRole('dialog', {name:'结果明细'})).toBeTruthy()
    expect(screen.getAllByText('有功损耗').length).toBeGreaterThan(0)
  })
  it('opens only real sources in an answer-owned sheet while execution stays in the conversation', () => {
    const events = [
      event('command_accepted', 1, {kind:'send_auto',text:'检查第一个对象'}, 'source_one'),
      event('tool_completed', 2, {tool_name:'grid_context_get',ok:true}, 'source_one'),
      event('attempt_completed', 3, {answer:'第一份回答',evidence_refs:['evidence:one'],admission:{mode:'authority_backed',assurance:'lineage_verified'}}, 'source_one'),
      event('command_accepted', 4, {kind:'send_auto',text:'检查第二个对象'}, 'source_two'),
      event('attempt_completed', 5, {answer:'第二份回答',evidence_refs:['evidence:two'],admission:{mode:'authority_backed',assurance:'lineage_verified'}}, 'source_two'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)} onSend={async()=>{}} onCancel={async()=>{}} />)
    const sources=screen.getAllByRole('button',{name:'查看推演证据'})
    sources[0].focus();fireEvent.click(sources[0])
    expect(screen.getByRole('dialog',{name:'推演依据'}).textContent).toContain('检查第一个对象')
    expect(screen.getByRole('dialog').textContent).not.toContain('evidence:two')
    fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'})
    expect(document.activeElement).toBe(sources[0])
    fireEvent.click(sources[1])
    expect(screen.getAllByRole('dialog')).toHaveLength(1)
    expect(screen.getByRole('dialog').textContent).toContain('检查第二个对象')
    expect(screen.getByRole('dialog').textContent).not.toContain('evidence:one')
    fireEvent.click(screen.getByRole('button',{name:'关闭推演依据'}))
    fireEvent.click(screen.getByRole('button',{name:'查看执行过程'}))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.querySelector('.capstone-chat-activity-attached[open]')).toBeTruthy()
  })
  it('shows only available answer actions for a plain reply without products or records', () => {
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '彩虹由水滴折射与色散形成。', admission: { mode: 'offline_information', assurance: 'general_knowledge' } }, 'plain')]}
      disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(within(screen.getByLabelText('回答操作')).getAllByRole('button').map(button => button.getAttribute('aria-label'))).toEqual(['复制回答'])
  })
  it('combines real network, result, record, process and retry actions on the same reply', () => {
    const events = [event('command_accepted', 1, {kind:'send_auto', text:'检查当前模型'}, 'combined'),
      event('tool_completed', 2, {tool_name:'grid_analysis_run', tool_call_id:'run', ok:false, failure:{code:'invalid_arguments', message:'需要核对参数'}}, 'combined'),
      event('attempt_completed', 3, {answer:'已记录检查结果。'}, 'combined')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)}
      networkAttemptIds={['combined']}
      onShowNetwork={vi.fn()} onReadAttemptRecords={vi.fn()} onRegenerate={vi.fn()} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.queryByRole('button', { name: '查看推演证据' })).toBeNull()
    expect(screen.queryByRole('button', { name: '查看执行过程' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '更多回答操作' })).toBeNull()
    expect([...screen.getByLabelText('回答操作').querySelectorAll('button')].every(button => !button.disabled)).toBe(true)
  })
  it('uses accepted runtime authors for streaming and completed answers across mode switches', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', text: '专业任务', runtime_mode: 'capstone' }, 'business'),
      event('attempt_completed', 2, { answer: '专业结果' }, 'business'),
      event('command_accepted', 3, { kind: 'send_auto', text: '日常任务', runtime_mode: 'pi_reference' }, 'general'),
      event('assistant_text_delta', 4, { text: '通用结果' }, 'general'),
    ]
    const props = { events, disabled: false, isRunning: true, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const view = render(<CapstoneAssistantThread {...props} runtimeMode="pi_reference" />)
    const authors = () => screen.getAllByLabelText('智能体回答').map(node => node.querySelector('.capstone-chat-role')?.textContent)
    expect(authors()).toEqual(['CAPSTONE', 'Pi'])
    expect(document.querySelector('.capstone-assistant-runtime-label')?.textContent).toBe('Pi实时响应')
    view.rerender(<CapstoneAssistantThread {...props} runtimeMode="capstone" isRunning={false}
      events={[...events, event('attempt_completed', 5, { answer: '通用结果' }, 'general')]} />)
    expect(authors()).toEqual(['CAPSTONE', 'Pi'])
    expect(document.querySelector('.capstone-assistant-runtime-label')?.textContent).toContain('CAPSTONE')
  })
  it('keeps the original diagnostic available from the compact failure reason', () => {
    render(<CapstoneAssistantThread events={[
      event('tool_completed', 1, { tool_name: 'grid_result_dataset_query', tool_call_id: 'bad-field', ok: false,
        failure: { code: 'result_field_unavailable', message: 'Result query references fields not present in the described dataset',
          summary: '字段不可用：bus；可用字段：index、vm_pu' } }, 'failure'),
      event('attempt_completed', 2, { answer: '已改用正确字段查询。' }, 'failure'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    const reason = screen.getByText('字段不可用：bus；可用字段：index、vm_pu')
    expect(reason.title).toContain('Result query references fields not present in the described dataset')
    expect(reason.closest('.capstone-tool-call-content')).toBeTruthy()
    expect(screen.queryByText('查询字段不存在')).toBeNull()
    const trigger = screen.getByRole('button', { name: '查看原始诊断' })
    fireEvent.click(trigger)
    expect(screen.getByRole('tooltip').textContent).toContain('Result query references fields not present in the described dataset')
  })
  it('connects real failed calls to the next step and shows the recorded method adjustment', () => {
    const first = { id: 'read', number: 1, title: '读取已有结果', status: 'completed' }
    const next = { id: 'query', number: 2, title: '查询结果数据集', status: 'completed', after_failed_steps: ['read'] }
    render(<CapstoneAssistantThread events={[
      event('tool_started', 1, { tool_name: 'grid_result_branches_rank', tool_call_id: 'rank', task_step_id: 'read', task_step: first }, 'recover'),
      event('tool_completed', 2, { tool_name: 'grid_result_branches_rank', tool_call_id: 'rank', task_step_id: 'read', ok: false, failure: { code: 'result_not_rankable', message: 'Result does not publish branch data' } }, 'recover'),
      event('runtime_action', 3, { task_step: next }, 'recover'),
      event('tool_completed', 4, { tool_name: 'agent_task_progress', capability: 'agent_task_progress', ok: true, task_step_id: 'query', task_progress: { kind: 'adjustment', text: '排名不可用，改从数据集取数。', refs: [] } }, 'recover'),
      event('attempt_completed', 5, { answer: '已读取可用数据。', task_steps: [first, next] }, 'recover'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    expect(screen.getByText('该结果没有可用于支路排名的数据。')).toBeTruthy()
    expect(screen.getByText('接续 01')).toBeTruthy()
    expect(screen.getByText(/排名不可用，改从数据集取数/)).toBeTruthy()
    expect(screen.queryByText('已重新规划')).toBeNull()
  })
  it('keeps the last recorded work visible after failure without inventing completion', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_started', 1, {}, 'unfinished'),
      event('tool_completed', 2, { tool_name: 'agent_task_progress', capability: 'agent_task_progress', ok: true,
        task_progress: { kind: 'observation', text: '已生成图表，正在组装报告。', refs: [] } }, 'unfinished'),
      event('attempt_failed', 3, { message: '执行中断' }, 'unfinished'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByLabelText('中断前的工作记录').textContent).toContain('已生成图表，正在组装报告。')
    expect(screen.queryByText('报告已完成')).toBeNull()
  })
  it('shows host preparation and terminal timing even before any tool call', () => {
    const preparation = { id: 'task-preparation', number: 1, title: '任务准备', status: 'running' }
    const events = [event('attempt_started', 1, { task_step: preparation }, 'stages'),
      event('attempt_completed', 2, { answer: '任务已结束。', task_steps: [{ ...preparation, status: 'completed', duration_ms: 7000 }, { id: 'closing', number: 2, title: '核验与结果整理', status: 'completed', duration_ms: 2000 }] }, 'stages')]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const button = screen.getByRole('button', { name: '查看执行过程' }) as HTMLButtonElement
    expect(button.disabled).toBe(false)
    fireEvent.click(button)
    expect(screen.getByText('任务准备')).toBeTruthy()
    expect(screen.getByText('核验与结果整理')).toBeTruthy()
    expect(screen.getByText('7.0s')).toBeTruthy()
  })
  it('keeps fold controls in the summary and disables them from actual step state', () => {
    const events = [event('attempt_started', 1, {}, 'fold'),
      event('tool_completed', 2, { tool_name: 'grid_context_get', tool_call_id: 'one', ok: true, task_step: { id: 'first', number: 1, title: '检查', status: 'completed', duration_ms: 1000 } }, 'fold'),
      event('runtime_action', 3, { task_step: { id: 'last', number: 2, title: '生成回复', status: 'completed', duration_ms: 2000 } }, 'fold'),
      event('attempt_completed', 4, { answer: '检查完成。' }, 'fold')]
    const { container } = render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    const expand = screen.getByRole('button', { name: '展开步骤' }) as HTMLButtonElement
    const collapse = screen.getByRole('button', { name: '折叠步骤' }) as HTMLButtonElement
    const frame = container.querySelector<HTMLDetailsElement>('.capstone-chat-activity-attached')!
    expect(expand.closest('summary')).toBe(frame.querySelector(':scope > summary'))
    expect(frame.querySelector(':scope > summary')!.textContent).not.toContain('查看执行过程')
    expect(expand.disabled).toBe(false)
    expect(collapse.disabled).toBe(true)
    fireEvent.click(expand)
    expect(expand.disabled).toBe(true)
    expect(collapse.disabled).toBe(false)
    fireEvent.click(collapse)
    const steps = [...container.querySelectorAll<HTMLDetailsElement>('.capstone-business-step')]
    expect(steps.every(step => !step.open)).toBe(true)
    expect(frame.open).toBe(true)
    expect(collapse.disabled).toBe(true)
    expect(expand.disabled).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: '展开步骤：检查' }))
    expect(expand.disabled).toBe(false)
    expect(collapse.disabled).toBe(false)
    fireEvent.click(expand)
    expect(screen.getByRole('button', { name: '折叠步骤：检查' }).getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('button', { name: '折叠步骤：生成回复' }).getAttribute('aria-expanded')).toBe('true')
    expect(expand.disabled).toBe(true)
  })
  it('positions a new running instruction near the top even when it was already visible', async () => {
    const scroll = vi.spyOn(HTMLElement.prototype, 'scrollTo')
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const viewport = document.querySelector('.capstone-chat-viewport')
      const top = this.classList.contains('capstone-chat-viewport') ? 100 : 400 - (viewport?.scrollTop || 0)
      return { top, bottom: top + (this === viewport ? 500 : 40), left: 0, right: 800, width: 800, height: this === viewport ? 500 : 40, x: 0, y: top, toJSON: () => ({}) }
    })
    try {
      const events = [event('command_accepted', 1, {kind:'send_auto',text:'读取线路参数'}, 'anchor'), event('attempt_started', 2, {}, 'anchor')]
      render(<CapstoneAssistantThread events={events} activity={[]} disabled={false} isRunning onSend={async()=>{}} onCancel={async()=>{}} />)
      const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
      Object.defineProperties(viewport, {clientHeight:{configurable:true,value:500},scrollHeight:{configurable:true,value:800}})
      await waitFor(() => expect(scroll).toHaveBeenCalledWith({ top: 292, behavior: 'smooth' }))
    } finally { rect.mockRestore(); scroll.mockRestore() }
  })
  it('keeps both running process views readable when the bottom of the message has little space', async () => {
    let bottom = 500, processOffset = 0
    const rect = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const top = this.classList.contains('capstone-chat-viewport') ? 100 : 280 - processOffset
      return { top, bottom, left: 0, right: 800, width: 800, height: bottom - top, x: 0, y: top, toJSON: () => ({}) }
    })
    try {
      const events = [event('attempt_started', 1, {}, 'fit'), event('tool_started', 2, {tool_name: 'grid_context_get'}, 'fit')]
      render(<CapstoneAssistantThread events={events} activity={projectAssistantActivity(events)} disabled={false} isRunning onSend={async()=>{}} onCancel={async()=>{}} />)
      const preview = screen.getByLabelText('执行过程预览')
      expect(preview.style.maxHeight).toBe('208px')
      bottom = 360
      fireEvent.resize(window)
      expect(preview.style.maxHeight).toBe('80px')
      fireEvent.click(document.querySelector('.capstone-chat-activity-attached > summary')!)
      await waitFor(() => expect((document.querySelector('.capstone-complete-process') as HTMLElement)?.style.maxHeight).toBe('80px'))
      bottom = 1200
      fireEvent.resize(window)
      const maximum = Math.min(1100 * .72, window.innerHeight * .65)
      const body = document.querySelector('.capstone-complete-process') as HTMLElement
      expect(Number.parseFloat(body.style.maxHeight)).toBeLessThanOrEqual(maximum)
      processOffset = 400
      fireEvent.scroll(document.querySelector('.capstone-chat-viewport')!)
      expect(Number.parseFloat(body.style.maxHeight)).toBeLessThanOrEqual(maximum)
      const height = body.style.maxHeight
      processOffset = 800
      fireEvent.scroll(document.querySelector('.capstone-chat-viewport')!)
      expect(body.style.maxHeight).toBe(height)
    } finally { rect.mockRestore() }
  })
  it('keeps all actions and a separate committed work explanation in the height-limited running window', () => {
    const snapshot = { research_id: 'research-1', revision: 1, goal: '核验故障影响', condition_refs: [], claims: [],
      notes: [{ note_id: 'finding', text: '已取得拓扑结果，继续检查失供范围。', refs: ['result:topology'] }], open_questions: [] }
    const events = [event('attempt_started', 1, {}, 'study'),
      event('research_state_updated', 2, { research_id: snapshot.research_id, research_revision: 1,
        goal: snapshot.goal, current_note_ids: ['finding'], research_snapshot: snapshot }, 'study'),
      ...Array.from({ length: 12 }, (_, index) => event('tool_completed', index + 3,
        { tool_name: `grid_check_${index}`, tool_call_id: `call_${index}`, ok: true }, 'study'))]
    const props = { disabled: false, isRunning: true, onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={events} activity={projectAssistantActivity(events)} />)
    const preview = screen.getByLabelText('执行过程预览')
    expect(preview.querySelectorAll('.capstone-chat-activity-item')).toHaveLength(12)
    expect(within(preview).getByText(snapshot.notes[0].text)).toBeTruthy()
    expect(preview.textContent).toContain('grid_check_0')
    expect(preview.textContent).toContain('grid_check_11')
    Object.defineProperties(preview, { scrollHeight: { configurable: true, value: 600 }, clientHeight: { configurable: true, value: 320 } })
    const append = (sequence: number) => {
      events.push(event('tool_completed', sequence, { tool_name: 'grid_query', tool_call_id: `extra_${sequence}`, ok: true }, 'study'))
      rerender(<CapstoneAssistantThread {...props} events={[...events]} activity={projectAssistantActivity(events)} />)
    }
    append(50)
    expect(preview.scrollTop).toBe(280)
    preview.scrollTop = 40
    fireEvent.scroll(preview)
    append(51)
    expect(preview.scrollTop).toBe(40)
    preview.scrollTop = 280
    fireEvent.scroll(preview)
    Object.defineProperty(preview, 'scrollHeight', { configurable: true, value: 700 })
    append(52)
    expect(preview.scrollTop).toBe(380)
  })
  it('shows actual reply completion time and distinct tool sources', () => {
    const finished = '2026-10-13T05:12:34Z'
    const events = [event('attempt_started', 1, {}, 'study'),
      event('tool_completed', 2, { tool_name: 'agent_research_read', tool_call_id: 'one', ok: true }, 'study'),
      event('tool_completed', 3, { tool_name: 'grid_context_get', tool_call_id: 'two', binding_id: 'grid', capability: 'context.get', ok: true }, 'study'),
      event('attempt_completed', 4, { answer: '检查结束。' }, 'study', finished)]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)} onSend={async () => {}} onCancel={async () => {}} />)
    const time = screen.getByLabelText(/^回答完成时间：/)
    expect(time.getAttribute('datetime')).toBe(finished)
    expect(time.textContent).toMatch(/\d{2}:\d{2}:34/)
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    expect(screen.getByText('CAPSTONE', { selector: '.capstone-chat-activity-source' })).toBeTruthy()
    expect(screen.getByText('GRID', { selector: '.capstone-chat-activity-source' })).toBeTruthy()
  })
  it('keeps the unfinished followup entry hidden without sending an instruction', () => {
    const followup = vi.fn(), send = vi.fn()
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '旧回答。' }, 'attempt_old')]}
      disabled={false} isRunning={false} activity={[]} onSend={send} onCancel={async () => {}} onFollowup={followup} />)
    expect(screen.queryByRole('button', { name: '追问此任务' })).toBeNull()
    expect(followup).not.toHaveBeenCalled()
    expect(send).not.toHaveBeenCalled()
  })
  it('shows a research continuation as an action without presenting a calculation', () => {
    const actions = projectAssistantActivity([event('research_step_resumed', 1,
      { reason: 'model_step_budget', budget_seconds: 90 }, 'attempt_research')])
    expect(actions).toMatchObject([{ label: '推理等待达到时限，继续当前会话', source: 'capstone · research', status: 'completed' }])
  })
  it('opens saved records for the original answer without submitting an instruction', async () => {
    const onSend = vi.fn()
    const read = vi.fn().mockResolvedValue({ threadId: 'thr_demo', attemptId: 'attempt_old',
      instruction: '原任务', modelContext: null, events: [], nextAfter: 0, hasMore: false })
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '已完成。' }, 'attempt_old')]}
      disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}}
      onReadAttemptRecords={read} />)
    fireEvent.click(screen.getByRole('button', { name: '查看执行过程' }))
    expect(read).not.toHaveBeenCalled()
    expect(screen.queryByText(/已完成.*工具调用数未记录/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }))
    await screen.findByText('原任务')
    expect(read).toHaveBeenCalledWith('attempt_old', 0)
    expect(onSend).not.toHaveBeenCalled()
  })
  it('binds semantic invocation receipts to their original task without copying native args', () => {
    const messages = projectAssistantMessages([
      event('attempt_started', 1, {}, 'calculation'),
      event('tool_started', 2, { tool_name: 'bash', args: { command: 'private command' } }, 'calculation'),
      event('tool_completed', 3, { tool_call_id: 'call-1', tool_name: 'grid_analysis_run', capability: 'analysis.run',
        ok: false, request_parameters: { operation: 'powerflow.ac' } }, 'calculation'),
      event('attempt_completed', 4, { answer: '计算未完成。' }, 'calculation'),
      event('attempt_completed', 5, { answer: '其他回答。' }, 'other'),
    ])
    expect(messages.find(message => message.id === 'assistant-calculation')?.metadata?.custom?.toolExecutions)
      .toEqual([{ id: 'call-1', tool: 'grid_analysis_run', capability: 'analysis.run', ok: false,
        parameters: { operation: 'powerflow.ac' }, resultRefs: [], evidenceRefs: [], sequence: 3 }])
    expect(messages.find(message => message.id === 'assistant-other')?.metadata?.custom?.toolExecutions).toEqual([])
  })

  it('keeps committed research records scoped to the task and opens them without simulation evidence', () => {
    const snapshot = { research_id: 'research-1', revision: 1, goal: '比较场景', condition_refs: [],
      claims: [{ claim_id: 'claim-1', statement: '还需核验边界', status: 'pending', refs: [] }], notes: [], open_questions: [] }
    render(<CapstoneAssistantThread events={[
      event('attempt_started', 1, {}, 'study'),
      event('research_state_updated', 2, { research_id: 'research-1', research_revision: 1,
        goal: '比较场景', research_snapshot: snapshot }, 'study'),
      event('attempt_completed', 3, { answer: '检查尚未完成。' }, 'study'),
      event('attempt_completed', 4, { answer: '另一个任务。' }, 'other'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const buttons = screen.getAllByRole('button', { name: '查看执行过程' }) as HTMLButtonElement[]
    expect(buttons.map(button => button.disabled)).toEqual([false])
    fireEvent.click(buttons[0])
    fireEvent.click(screen.getAllByRole('button', { name: '放大阅读执行过程' })[0])
    fireEvent.click(screen.getByText('研究判断与工作记录 · 修订 1'))
    expect(screen.getByText('还需核验边界')).toBeTruthy()
  })

  it('retains a research-record goal without labelling it the current instruction goal', () => {
    const events = [
      event('attempt_started', 1, {}, 'study'),
      event('research_state_updated', 2, { goal: '比较方案并核验可行性' }, 'study'),
      event('attempt_completed', 3, { answer: '已完成比较。' }, 'study'),
      event('attempt_completed', 4, { answer: '另一任务的回答。' }, 'other'),
    ]
    const messages = projectAssistantMessages(events)
    expect(messages.find(message => message.id === 'assistant-study')?.metadata?.custom?.retainedResearchGoal).toBe('比较方案并核验可行性')
    expect(messages.find(message => message.id === 'assistant-study')?.metadata?.custom?.researchGoal).toBeUndefined()
    expect(messages.find(message => message.id === 'assistant-other')?.metadata?.custom?.researchGoal).toBeUndefined()
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getAllByText('研究记录中的目标')).toHaveLength(1)
    expect(screen.queryByText('本次任务的研究目标')).toBeNull()
  })
  it('includes failed execution and validation records in calculation results', () => {
    const events = [
      event('attempt_started', 1, {}, 'study'),
      event('tool_completed', 2, { tool_name: 'grid_analysis_run', tool_call_id: 'run-1', ok: false, failure: { code: 'invalid_arguments', phase: 'validate', message: '缺少所需输入。' } }, 'study'),
      event('validation_observation', 3, { status: 'failed', stage: 'answer_check', code: 'answer_admission_failed', message: '回答核验未通过，原始内容和执行记录已保留。' }, 'study'),
      event('attempt_completed', 4, { answer: '计算未完成；已记录失败步骤。', admission: { mode: 'limited', assurance: 'limited' } }, 'study'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '查看计算结果' }))
    expect(screen.getByText('执行失败')).toBeTruthy()
    expect(within(screen.getByText('执行失败').closest('section')!).getByText('grid_analysis_run')).toBeTruthy()
    expect(within(screen.getByText('执行失败').closest('section')!).getByText('缺少所需输入。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /失败 02.*核验未通过/ }))
    expect(screen.getByText('核验未通过')).toBeTruthy()
    expect(screen.getByText('未作为已验证结论使用。')).toBeTruthy()
  })
  it('shows the delivered partial outcome instead of replacing it with an error code', () => {
    const answer = '已保存潮流结果。后续检查中断，尚不能判断整个任务是否满足要求。'
    const events = [
      event('attempt_completed', 1, { answer: '此前回答仍保留。' }, 'previous'),
      event('attempt_started', 2, {}, 'partial'),
      event('tool_completed', 3, { tool_name: 'grid_powerflow_run', ok: true }, 'partial'),
      event('attempt_failed', 4, { answer, error_code: 'runtime_failed', outcome: { status: 'partial' }, admission: { mode: 'authority_backed', assurance: 'lineage_verified' }, evidence_refs: ['evidence:1'] }, 'partial'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText(answer)).toBeTruthy()
    expect(screen.getByText('此前回答仍保留。')).toBeTruthy()
    expect(screen.queryByText('执行失败')).toBeNull()
    expect(projectAssistantMessages(events).find(item => item.id === 'assistant-partial')?.metadata?.custom?.toolCount).toBe(1)
  })
  it('renders an admitted limited answer and keeps prior answers and execution records', () => {
    const answer = '已完成模型检查。当前没有可用的稳定性计算方法，因此尚不能判断稳定裕度。'
    const events = [
      event('attempt_completed', 1, { answer: '此前已完成的回答。' }, 'previous'),
      event('command_accepted', 2, { kind: 'send_professional', text: '评估当前模型' }, 'limited'),
      event('attempt_started', 3, {}, 'limited'),
      event('tool_completed', 4, { tool_name: 'grid_model_describe', capability: 'model.describe', tool_call_id: 'inspect', ok: true }, 'limited'),
      event('attempt_completed', 5, { answer, admission: { mode: 'limited', assurance: 'limited' }, result_refs: [], evidence_refs: [] }, 'limited'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText(answer)).toBeTruthy()
    expect(screen.getByText('此前已完成的回答。')).toBeTruthy()
    expect(screen.queryByText('执行失败')).toBeNull()
    const message = projectAssistantMessages(events).find(item => item.id === 'assistant-limited')
    expect(message?.metadata?.custom?.admission).toEqual({ mode: 'limited', assurance: 'limited' })
    expect(message?.metadata?.custom?.toolCount).toBe(1)
  })

  it('places offscreen instructions at the reading start and preserves visible instructions, draft and input focus', () => {
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '定位这条指令' }, 'first'), event('attempt_completed', 2, { answer: '回答。'.repeat(160) }, 'first')]
    const props = { events, disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '保留草稿' } })
    input.focus()
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 10000 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 })
    const instruction = screen.getByLabelText('用户指令')
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(rect(100, 400))
    const position = vi.spyOn(instruction, 'getBoundingClientRect').mockReturnValue(rect(150, 40))
    viewport.scrollTop = 200
    rerender(<CapstoneAssistantThread {...props} instructionLocation={{ attemptId: 'first', nonce: 1 }} />)
    expect(viewport.scrollTop).toBe(200)
    position.mockReturnValue(rect(50, 40))
    rerender(<CapstoneAssistantThread {...props} instructionLocation={{ attemptId: 'first', nonce: 2 }} />)
    expect(viewport.scrollTop).toBe(134)
    position.mockReturnValue(rect(550, 40))
    rerender(<CapstoneAssistantThread {...props} instructionLocation={{ attemptId: 'first', nonce: 3 }} />)
    expect(viewport.scrollTop).toBe(568)
    expect(document.activeElement).toBe(input)
    expect(input.value).toBe('保留草稿')
    expect(screen.getByRole('button', { name: '展开完整回答' })).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} instructionLocation={{ attemptId: 'unrelated', nonce: 4 }} />)
    expect(viewport.scrollTop).toBe(568)
  })
  it('keeps a requested older instruction mounted in the continuous history view', () => {
    const events = Array.from({ length: 55 }, (_, index) => [event('command_accepted', index * 2 + 1, { kind: 'send_auto', text: `定位窗口指令 ${index}` }, `attempt_${index}`), event('attempt_completed', index * 2 + 2, { answer: `回答 ${index}` }, `attempt_${index}`)]).flat()
    const props = { events, disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    expect(screen.getByText('定位窗口指令 0')).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} instructionLocation={{ attemptId: 'attempt_0', nonce: 1 }} />)
    expect(screen.getByText('定位窗口指令 0')).toBeTruthy()
  })

  it('shows the instruction model short name and preserves its historical binding after switching', () => {
    const first = { ...event('command_accepted', 1, { kind: 'send_auto', text: '检查电压' }, 'first'), modelContextId: 'ctx_a' }
    const switchEvent = event('model_context_activated', 2, { previous_context: { id: 'ctx_a', model_id: 'ieee39' }, model_context: { id: 'ctx_b', model_id: 'case57' } })
    const second = { ...event('command_accepted', 3, { kind: 'send_auto', text: '检查负荷' }, 'second'), modelContextId: 'ctx_b' }
    const props = { events: [first], instructionModels: [{ contextId: 'ctx_a', modelId: 'ieee39' }], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    expect(within(screen.getByLabelText('用户指令')).getByText('IEEE-39')).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} events={[first, switchEvent, second]} instructionModels={[{ contextId: 'ctx_b', modelId: 'case57' }]} />)
    const instructions = screen.getAllByLabelText('用户指令')
    expect(within(instructions[0]).getByText('IEEE-39')).toBeTruthy()
    expect(within(instructions[1]).getByText('case57')).toBeTruthy()
    expect(projectAssistantMessages([first, switchEvent, second])[0].metadata?.custom?.modelId).toBe('ieee39')
  })
  it('shows the accepted instruction time without changing it on refresh', () => {
    const sentAt = '2026-10-08T01:24:23Z'
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '打开 IEEE-39' }, 'first', sentAt)]
    const props = { events, disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    const instruction = screen.getByLabelText('用户指令')
    const time = instruction.querySelector('time')
    expect(time?.getAttribute('datetime')).toBe(sentAt)
    expect(time?.getAttribute('title')).toContain('2026')
    expect(time?.textContent).toMatch(/\d{2}:\d{2}$/)
    const label = time?.textContent
    rerender(<CapstoneAssistantThread {...props} />)
    expect(screen.getByLabelText('用户指令').querySelector('time')?.textContent).toBe(label)
    expect(projectAssistantMessages(events)[0].metadata?.custom?.sentAt).toBe(sentAt)
  })
  it('keeps recovery available after a diagnostic cursor and excludes it from an older history page', () => {
    const props = { events: [event('attempt_completed', 2, { answer: '已完成回答' }, 'first')],
      systemNotices: [{ id: 'connection', afterEventSeq: 3, text: '连接需要恢复', tone: 'error' as const, action: 'reconnect' as const }],
      disabled: true, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    expect(screen.getByRole('button', { name: '重新连接' })).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} historyAtLatest={false} />)
    expect(screen.queryByRole('button', { name: '重新连接' })).toBeNull()
  })

  it('positions local system notices between instructions and preserves them without answer actions', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '第一条指令' }, 'first'),
      event('attempt_completed', 2, { answer: '第一条回答' }, 'first'),
      event('command_accepted', 3, { kind: 'send_auto', text: '第二条指令' }, 'second'),
      event('attempt_completed', 4, { answer: '第二条回答' }, 'second'),
    ]} systemNotices={[{ id: 'rejected', afterEventSeq: 2, text: '本次指令未发送，输入已保留。', tone: 'error' }]}
      disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const notice = screen.getByText('本次指令未发送，输入已保留。').closest('[data-message-id]') as HTMLElement
    expect(notice.classList.contains('is-system')).toBe(true)
    const nodes = [...document.querySelectorAll('[data-message-id]')]
    expect(nodes.indexOf(notice)).toBe(2)
    expect(within(notice).queryByRole('button', { name: '复制回答' })).toBeNull()
    expect(within(notice).queryByRole('button', { name: '查看分析证据' })).toBeNull()
  })

  it('shows a failure once as a system notice after any partial answer', () => {
    render(<CapstoneAssistantThread events={[
      event('assistant_text_delta', 1, { text: '尚未完成的分析说明。' }, 'failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed' }, 'failed'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('尚未完成的分析说明。')).toBeTruthy()
    const failure = screen.getByText('执行失败').closest('.capstone-system-notice')
    expect(failure).toBeTruthy()
    expect(screen.getAllByText('执行失败')).toHaveLength(1)
  })
  it('offers admitted evidence without unrelated disabled actions on other replies', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '有已准入证据。', evidence_refs: ['evidence:1'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'available'),
      event('attempt_completed', 2, { answer: '普通信息回答。', admission: { mode: 'offline_information', assurance: 'general_knowledge' } }, 'information'),
      event('attempt_failed', 3, { error_code: 'capability_required' }, 'missing'),
      event('attempt_failed', 4, { error_code: 'answer_admission_failed' }, 'unavailable'),
      event('assistant_text_delta', 5, { text: '还在计算。' }, 'pending'),
    ]} disabled={false} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const actions = screen.getAllByRole('button', { name: '查看推演证据' }) as HTMLButtonElement[]
    expect(actions.map((action) => action.dataset.evidenceState)).toEqual(['available'])
    expect(actions.map((action) => action.disabled)).toEqual([false])
    expect(actions[0].title).toContain('查看推演证据')
    fireEvent.click(actions[0])
    expect(screen.getByRole('region', { name: '推演证据' }).textContent).toContain('evidence:1')
  })
  it('uses the committed answer instead of provisional streamed text', () => {
    const messages = projectAssistantMessages([
      event('assistant_text_delta', 1, { text: '临时不完整回答。' }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '完整正式回答。', answer_summary: '正式回答。' }, 'attempt_1'),
    ])
    expect(messages[0].content).toEqual([{ type: 'text', text: '完整正式回答。' }])
    expect(messages[0].metadata?.custom?.answerSummary).toBeUndefined()
  })

  it('organizes existing answers once and leaves new answers and drafts intact', () => {
    const answer = '已有结论。\n\n' + '完整条件。'.repeat(160)
    const onSend = vi.fn()
    const props = { events: [event('attempt_completed', 1, { answer }, 'attempt_1')], disabled: false, isRunning: false, activity: [], onSend, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} storageKey="reading_thread" />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '下一条草稿' } })
    expect(screen.queryByRole('combobox', { name: '回答显示模式' })).toBeNull()
    const menu = screen.getByRole('button', { name: '对话设置' })
    expect(menu.closest('.capstone-composer-footer')).toBeTruthy()
    const first = screen.getByText(/完整条件。完整条件/).closest('.capstone-chat-message')!
    expect(within(first as HTMLElement).getByRole('button', { name: '折叠回答' }).getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(first.querySelector('.capstone-answer-content')?.getAttribute('aria-hidden')).toBe('true')
    rerender(<CapstoneAssistantThread {...props} storageKey="reading_thread" events={[
      ...props.events, event('attempt_completed', 2, { answer: '后续结论。\n\n' + '后续条件。'.repeat(160) }, 'attempt_2'),
    ]} />)
    expect(screen.getByText('后续结论。')).toBeTruthy()
    expect(screen.getByText(/后续条件。后续条件/).closest('.capstone-answer-content')?.getAttribute('aria-hidden')).toBeNull()
    expect(within(first as HTMLElement).getByRole('button', { name: '展开完整回答' })).toBeTruthy()
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '展开完整回答' }))
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '折叠回答' }))
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '展开历史回答' }))
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(2)
    expect(input.value).toBe('下一条草稿')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('ignores old mode preferences and keeps short answers and failure recovery visible', () => {
    sessionStorage.setItem('old_reading.readingMode', 'compact')
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '没有摘要的正式回答。' }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '保留正式事实。', answer_summary: '额外虚构数值。' }, 'attempt_2'),
      event('assistant_text_delta', 3, { text: '进行中。'.repeat(100) }, 'pending'),
      event('attempt_failed', 4, { error_code: 'capability_required' }, 'failed'),
    ]} storageKey="old_reading" disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(screen.getByText('没有摘要的正式回答。')).toBeTruthy()
    expect(screen.getByText('保留正式事实。')).toBeTruthy()
    expect(screen.queryByText('额外虚构数值。')).toBeNull()
    expect(screen.queryByRole('button', { name: '展开完整回答' })).toBeNull()
    expect(screen.getByText(/进行中。进行中/)).toBeTruthy()
    expect(screen.getByText(/本次回答缺少所需的权威系统校验/)).toBeTruthy()
    sessionStorage.removeItem('old_reading.readingMode')
  })

  it('anchors repeated history actions to the visible instruction instead of the preceding long answer', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '之前的指令' }, 'first'),
      event('attempt_completed', 2, { answer: '之前的长回答。'.repeat(100) }, 'first'),
      event('command_accepted', 3, { kind: 'send_auto', text: '当前阅读的指令' }, 'second'),
      event('attempt_completed', 4, { answer: '当前的长回答。'.repeat(100) }, 'second'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const preceding = document.querySelector('[data-message-id="assistant-first"]') as HTMLElement
    const question = document.querySelector('[data-message-id="user-evt_3"]') as HTMLElement
    const current = document.querySelector('[data-message-id="assistant-second"]') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    viewport.scrollTop = 5000
    Object.defineProperties(viewport, { clientHeight: { value: 500 }, scrollHeight: { value: 20000 } })
    vi.spyOn(viewport, 'getBoundingClientRect').mockImplementation(() => rect(0, 500))
    const folded = () => preceding.querySelector('.capstone-answer')?.getAttribute('data-answer-state') === 'collapsed'
    vi.spyOn(preceding, 'getBoundingClientRect').mockImplementation(() => rect(50 - viewport.scrollTop, folded() ? 250 : 5050))
    vi.spyOn(question, 'getBoundingClientRect').mockImplementation(() => rect((folded() ? 300 : 5100) - viewport.scrollTop, 40))
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect((folded() ? 360 : 5160) - viewport.scrollTop, folded() ? 250 : 5000))
    const menu = screen.getByRole('button', { name: '对话设置' })
    viewport.scrollTop = 6000
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '展开历史回答' }))
    expect(viewport.scrollTop).toBe(6000)
    viewport.scrollTop = 5000
    for (const fold of [true, false, true, true, false, false]) {
      fireEvent.click(menu)
      fireEvent.click(screen.getByRole('button', { name: fold ? '折叠历史回答' : '展开历史回答' }))
      expect(question.getBoundingClientRect().top).toBe(100)
      expect(document.activeElement).toBe(menu)
    }
    viewport.scrollTop -= 50
    fireEvent.click(menu)
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(question.getBoundingClientRect().top).toBe(150)
  })

  it('copies the full committed answer while its display is folded', async () => {
    const answer = '结论。\n\n' + '完整条件。'.repeat(160)
    const copy = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: copy } })
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer, answer_summary: '结论。' }, 'attempt_1')]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    fireEvent.click(screen.getByRole('button', { name: '复制回答' }))
    await waitFor(() => expect(copy).toHaveBeenCalledWith(answer))
  })

  it('does not fold an answer that completes after a bulk action', () => {
    const first = event('attempt_completed', 1, { answer: '历史回答。'.repeat(100) }, 'first')
    const pending = event('assistant_text_delta', 2, { text: '生成中。'.repeat(100) }, 'pending')
    const props = { events: [first, pending], disabled: false, isRunning: true, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    rerender(<CapstoneAssistantThread {...props} isRunning={false} events={[first, pending, event('attempt_completed', 3, { answer: '新完成回答。'.repeat(100) }, 'pending')]} />)
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(1)
  })

  it('clears folding when switching Threads or refreshing instead of saving a global preference', () => {
    const props = { events: [event('attempt_completed', 1, { answer: '完整回答。'.repeat(100) }, 'first')], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender, unmount } = render(<CapstoneAssistantThread {...props} storageKey="fold_thread_a" />)
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    expect(screen.getByRole('button', { name: '展开完整回答' })).toBeTruthy()
    rerender(<CapstoneAssistantThread {...props} storageKey="fold_thread_b" />)
    expect(screen.getByRole('button', { name: '折叠回答' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '折叠回答' }))
    unmount()
    render(<CapstoneAssistantThread {...props} storageKey="fold_thread_b" />)
    expect(screen.getByRole('button', { name: '折叠回答' })).toBeTruthy()
    expect(sessionStorage.getItem('fold_thread_b.readingMode')).toBeNull()
  })

  it('keeps loaded history continuous while folding answers and retaining individual overrides', () => {
    const events = Array.from({ length: 60 }, (_, index) => event('attempt_completed', index + 1, { answer: `历史 ${index}。` + '完整条件。'.repeat(100) }, `history_${index}`))
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText(/历史 0。/)).toBeTruthy()
    expect(screen.getByText(/历史 59。/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '对话设置' }))
    fireEvent.click(screen.getByRole('button', { name: '折叠历史回答' }))
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(60)
    fireEvent.click(screen.getAllByRole('button', { name: '展开完整回答' }).at(-1)!)
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: '展开完整回答' })).toHaveLength(59)
    // This state regression renders sixty long answers and performs repeated
    // accessibility queries; it does not define a browser response-time limit.
  }, 10_000)

  it('loads older history into the same conversation without hiding newer messages', async () => {
    const older = [event('attempt_completed', 1, { answer: '更早回答。' }, 'older')]
    const newer = [event('attempt_completed', 2, { answer: '最新回答。' }, 'newer')]
    const onLoadOlder = vi.fn().mockResolvedValue(undefined)
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onLoadOlder }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={newer} hasOlderHistory />)

    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    await waitFor(() => expect(onLoadOlder).toHaveBeenCalledTimes(1))
    rerender(<CapstoneAssistantThread {...props} events={[...older, ...newer]} hasOlderHistory={false} />)

    expect(screen.getByText('更早回答。')).toBeTruthy()
    expect(screen.getByText('最新回答。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '返回最新对话' })).toBeNull()
  })

  it('reloads the latest tail only after retention trimmed newer messages', () => {
    const onReturnLatest = vi.fn()
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '保留的旧回答。' }, 'older')]}
      historyAtLatest={false} onReturnLatest={onReturnLatest}
      disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    fireEvent.click(screen.getByRole('button', { name: '返回最新对话' }))

    expect(onReturnLatest).toHaveBeenCalledTimes(1)
  })

  it('scrolls to the restored latest tail after returning from trimmed history', async () => {
    const onReturnLatest = vi.fn()
    const older = [event('attempt_completed', 1, { answer: '保留的旧回答。' }, 'older')]
    const latest = [event('attempt_completed', 2, { answer: '最新恢复回答。' }, 'latest')]
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onReturnLatest }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={older} historyAtLatest={false} />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 9792 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 369 })
    viewport.scrollTop = 593

    fireEvent.click(screen.getByRole('button', { name: '返回最新对话' }))
    expect(onReturnLatest).toHaveBeenCalledTimes(1)
    rerender(<CapstoneAssistantThread {...props} events={latest} historyAtLatest />)
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    expect(screen.queryByRole('button', { name: '返回最新对话' })).toBeNull()
    expect(viewport.scrollTop).toBe(9423)
  })

  it('does not restart latest scrolling when live events arrive between animation frames', () => {
    let nextFrame = 0
    const frames = new Map<number, FrameRequestCallback>()
    const requestFrame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { frames.set(++nextFrame, callback); return nextFrame })
    const cancelFrame = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => { frames.delete(id) })
    const runFrame = () => {
      const callbacks = [...frames.values()]
      frames.clear()
      act(() => callbacks.forEach((callback) => callback(0)))
    }
    try {
      const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onReturnLatest: vi.fn() }
      const older = [event('attempt_completed', 1, { answer: '旧回答。' }, 'older')]
      const latest = [event('attempt_completed', 2, { answer: '最新回答。' }, 'latest')]
      const { rerender } = render(<CapstoneAssistantThread {...props} events={older} historyAtLatest={false} />)
      const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
      Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 9792 })
      Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 369 })

      fireEvent.click(screen.getByRole('button', { name: '返回最新对话' }))
      rerender(<CapstoneAssistantThread {...props} events={latest} historyAtLatest />)
      for (let index = 0; index < 8; index++) {
        runFrame()
        rerender(<CapstoneAssistantThread {...props} events={[...latest, event('tool_completed', 3 + index, { tool_name: 'tool' }, 'live')]} historyAtLatest />)
      }
      viewport.scrollTop = 593
      runFrame()

      expect(viewport.scrollTop).toBe(593)
    } finally {
      requestFrame.mockRestore()
      cancelFrame.mockRestore()
    }
  })

  it('honors explicit upward navigation before the final latest-restoration frame', () => {
    let nextFrame = 0
    const frames = new Map<number, FrameRequestCallback>()
    const requestFrame = vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { frames.set(++nextFrame, callback); return nextFrame })
    const cancelFrame = vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => { frames.delete(id) })
    const runFrame = () => {
      const callbacks = [...frames.values()]
      frames.clear()
      act(() => callbacks.forEach((callback) => callback(0)))
    }
    try {
      const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onReturnLatest: vi.fn() }
      const older = [event('attempt_completed', 1, { answer: '旧回答。' }, 'older')]
      const latest = [event('attempt_completed', 2, { answer: '最新回答。' }, 'latest')]
      const { rerender } = render(<CapstoneAssistantThread {...props} events={older} historyAtLatest={false} />)
      const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
      Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 9792 })
      Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 369 })

      fireEvent.click(screen.getByRole('button', { name: '返回最新对话' }))
      rerender(<CapstoneAssistantThread {...props} events={latest} historyAtLatest />)
      runFrame()
      fireEvent.wheel(viewport, { deltaY: -120 })
      viewport.scrollTop = 9303
      runFrame()

      expect(viewport.scrollTop).toBe(9303)
    } finally {
      requestFrame.mockRestore()
      cancelFrame.mockRestore()
    }
  })

  it('keeps the reading anchor when an older history load resolves after animation frames', async () => {
    let finishLoad: (() => void) | undefined
    const onLoadOlder = vi.fn(() => new Promise<void>((resolve) => { finishLoad = resolve }))
    const newer = [event('attempt_completed', 2, { answer: '最新回答。'.repeat(20) }, 'newer')]
    const older = [event('attempt_completed', 1, { answer: '更早回答。' }, 'older')]
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onLoadOlder }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={newer} hasOlderHistory />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 1200 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(rect(0, 400))
    const current = screen.getByText(/最新回答。/).closest('[data-message-id]') as HTMLElement
    let currentBaseTop = 420
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect(currentBaseTop - viewport.scrollTop, 240))
    viewport.scrollTop = 300

    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    await waitFor(() => expect(onLoadOlder).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    currentBaseTop = 620
    finishLoad?.()
    await onLoadOlder.mock.results[0].value
    rerender(<CapstoneAssistantThread {...props} events={[...older, ...newer]} hasOlderHistory={false} />)
    await waitFor(() => expect(screen.getByText('更早回答。')).toBeTruthy())
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    expect(viewport.scrollTop).toBe(500)
  })

  it('keeps the older-load anchor when live messages arrive before the older page', async () => {
    let finishLoad: (() => void) | undefined
    const onLoadOlder = vi.fn(() => new Promise<void>((resolve) => { finishLoad = resolve }))
    const currentAnswer = event('attempt_completed', 2, { answer: '当前回答。'.repeat(20) }, 'current')
    const liveAnswer = event('attempt_completed', 3, { answer: '实时回答。' }, 'live')
    const olderAnswer = event('attempt_completed', 1, { answer: '更早回答。' }, 'older')
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onLoadOlder }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={[currentAnswer]} hasOlderHistory />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 1600 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(rect(0, 400))
    const current = screen.getByText(/当前回答。/).closest('[data-message-id]') as HTMLElement
    let currentBaseTop = 420
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect(currentBaseTop - viewport.scrollTop, 240))
    viewport.scrollTop = 300

    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    await waitFor(() => expect(onLoadOlder).toHaveBeenCalledTimes(1))
    rerender(<CapstoneAssistantThread {...props} events={[currentAnswer, liveAnswer]} hasOlderHistory />)
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    currentBaseTop = 620
    finishLoad?.()
    await onLoadOlder.mock.results[0].value
    rerender(<CapstoneAssistantThread {...props} events={[olderAnswer, currentAnswer, liveAnswer]} hasOlderHistory={false} />)
    await waitFor(() => expect(screen.getByText('更早回答。')).toBeTruthy())
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    expect(viewport.scrollTop).toBe(500)
  })

  it('restores the older-load anchor when the message count does not change', async () => {
    let finishLoad: (() => void) | undefined
    const onLoadOlder = vi.fn(() => new Promise<void>((resolve) => { finishLoad = resolve }))
    const terminal = event('attempt_completed', 2, { answer: '完整回答。'.repeat(20) }, 'same')
    const olderDelta = event('assistant_text_delta', 1, { text: '较早片段。' }, 'same')
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onLoadOlder }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={[terminal]} hasOlderHistory />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 1200 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(rect(0, 400))
    const current = screen.getByText(/完整回答。/).closest('[data-message-id]') as HTMLElement
    let currentBaseTop = 420
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect(currentBaseTop - viewport.scrollTop, 240))
    viewport.scrollTop = 300

    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    await waitFor(() => expect(onLoadOlder).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    currentBaseTop = 620
    finishLoad?.()
    await onLoadOlder.mock.results[0].value
    rerender(<CapstoneAssistantThread {...props} events={[olderDelta, terminal]} hasOlderHistory={false} />)
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    expect(screen.getAllByLabelText('智能体回答')).toHaveLength(1)
    expect(viewport.scrollTop).toBe(500)
  })

  it('keeps the middle of a long answer in place while loading older history', async () => {
    let finishLoad: (() => void) | undefined
    const onLoadOlder = vi.fn(() => new Promise<void>((resolve) => { finishLoad = resolve }))
    const question = event('command_accepted', 2, { kind: 'send_auto', payload: { text: '阅读长回答' } }, 'long')
    const answer = event('attempt_completed', 3, { answer: '长回答。'.repeat(300) }, 'long')
    const olderAnswer = event('attempt_completed', 1, { answer: '更早回答。' }, 'older')
    const props = { disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onLoadOlder }
    const { rerender } = render(<CapstoneAssistantThread {...props} events={[question, answer]} hasOlderHistory />)
    const viewport = document.querySelector('.capstone-chat-viewport') as HTMLElement
    const rect = (top: number, height: number) => ({ top, bottom: top + height, height, left: 0, right: 500, width: 500, x: 0, y: top, toJSON: () => ({}) })
    Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: 3000 })
    Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: 400 })
    vi.spyOn(viewport, 'getBoundingClientRect').mockReturnValue(rect(0, 400))
    const user = screen.getByLabelText('用户指令')
    vi.spyOn(user, 'getBoundingClientRect').mockImplementation(() => rect(-820 - viewport.scrollTop, 40))
    const current = screen.getByText(/长回答。/).closest('[data-message-id]') as HTMLElement
    let answerBaseTop = -500
    vi.spyOn(current, 'getBoundingClientRect').mockImplementation(() => rect(answerBaseTop - viewport.scrollTop, 1800))
    viewport.scrollTop = 0

    fireEvent.click(screen.getByRole('button', { name: '查看之前的对话' }))
    await waitFor(() => expect(onLoadOlder).toHaveBeenCalledTimes(1))
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    answerBaseTop = -300
    finishLoad?.()
    await onLoadOlder.mock.results[0].value
    rerender(<CapstoneAssistantThread {...props} events={[olderAnswer, question, answer]} hasOlderHistory={false} />)
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))

    expect(viewport.scrollTop).toBe(200)
  })

  it('closes the history actions on Escape and outside clicks', () => {
    render(<CapstoneAssistantThread events={[event('attempt_completed', 1, { answer: '历史回答。' }, 'first')]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const button = screen.getByRole('button', { name: '对话设置' })
    fireEvent.click(button)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(button)
    fireEvent.click(button)
    fireEvent.pointerDown(document.body)
    expect(screen.queryByRole('group', { name: '历史回答整理' })).toBeNull()
  })

  it('keeps one persistent answer toggle and its focus through collapse and expansion', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', text: '检查这条用户指令的回答' }, 'first'),
      event('attempt_completed', 2, { answer: '完整回答。'.repeat(160) }, 'first'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(projectAssistantMessages(events)[1].metadata?.custom?.instructionMessageId).toBe('user-evt_1')
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    expect(toggle.textContent).toBe('')
    expect(toggle.title).toBe('收起回答')
    expect(toggle.querySelector('.lucide-chevron-up')).toBeTruthy()
    expect(toggle.closest('.capstone-answer-header')?.querySelector('.capstone-chat-role')?.textContent).toBe('CAPSTONE')
    toggle.focus()
    fireEvent.click(toggle)
    const folded = screen.getByRole('button', { name: '展开完整回答' }).closest('.capstone-answer')!
    expect(folded.getAttribute('data-answer-state')).toBe('collapsed')
    expect(within(folded as HTMLElement).queryByText('已折叠')).toBeNull()
    expect(screen.getByRole('button', { name: '展开完整回答' })).toBe(toggle)
    expect(toggle.title).toBe('展开完整回答')
    expect(toggle.textContent).toBe('')
    expect(toggle.querySelector('.lucide-chevron-down')).toBeTruthy()
    expect(document.activeElement).toBe(toggle)
    fireEvent.click(toggle)
    expect(document.activeElement).toBe(toggle)
    expect(screen.getAllByRole('button', { name: '折叠回答' })).toEqual([toggle])
    expect(screen.queryByRole('button', { name: '折叠回答并返回指令' })).toBeNull()
  })

  it('keeps the corresponding instruction visible while retaining toggle focus', () => {
    const events = [event('command_accepted', 1, { kind: 'send_auto', text: '窗口边界的用户指令' }, 'first'), event('attempt_completed', 2, { answer: '边界回答。'.repeat(160) }, 'first'), ...Array.from({length:49}, (_, i) => event('attempt_completed', i + 3, { answer: `其他回答 ${i}` }, `other_${i}`))]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('窗口边界的用户指令')).toBeTruthy()
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    toggle.focus()
    fireEvent.click(toggle)
    expect(screen.getByText('窗口边界的用户指令')).toBeTruthy()
    expect(document.activeElement?.getAttribute('aria-label')).toBe('展开完整回答')
  })

  it('keeps toggle focus when its instruction is not loaded instead of choosing another question', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', text: '无关用户指令' }, 'other'),
      event('attempt_completed', 2, { answer: '原始指令未加载的回答。'.repeat(100) }, 'missing_instruction'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const toggle = screen.getByRole('button', { name: '折叠回答' })
    toggle.focus()
    fireEvent.click(toggle)
    expect(document.activeElement).toBe(toggle)
  })
  it('clears a reconciled draft once and preserves a later draft', async () => {
    const props = { events: [], disabled: false, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {} }
    const { rerender } = render(<CapstoneAssistantThread {...props} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '已提交指令' } })
    const acceptedDraft = { text: '已提交指令', commandId: 'cmd_recovered' }
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={acceptedDraft} />)
    await waitFor(() => expect(input.value).toBe(''))
    fireEvent.change(input, { target: { value: '下一条草稿' } })
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={{ ...acceptedDraft }} />)
    expect(input.value).toBe('下一条草稿')
    rerender(<CapstoneAssistantThread {...props} acceptedDraft={{ text: '其他已提交指令', commandId: 'cmd_other' }} />)
    expect(input.value).toBe('下一条草稿')
  })
  it('disables a completed rerun when a new instruction is blocked or its model context is historical', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_1'),
      { ...event('attempt_completed', 2, { answer: '已完成。' }, 'attempt_1'), modelContextId: 'ctx_old' },
    ]
    const onRegenerate = vi.fn()
    const props = { events, isRunning: false, activity: [], onSend: async () => {}, onCancel: async () => {}, onRegenerate }
    const { rerender } = render(<CapstoneAssistantThread {...props} disabled={true} />)
    expect(screen.queryByRole('button', { name: '重试本次指令' })).toBeNull()
    rerender(<CapstoneAssistantThread {...props} disabled={false}
      modelSummary={{ modelId: 'case57', implementationFamily: 'pandapower', modelRevision: 'new', contextId: 'ctx_new' }} />)
    expect(screen.queryByRole('button', { name: '重试本次指令' })).toBeNull()
    expect(onRegenerate).not.toHaveBeenCalled()
  })
  it('does not expose unavailable product or execution actions on an informational answer', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '目录信息。' }, 'attempt_catalog'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const toolbar = screen.getByLabelText('回答操作')
    const buttons = within(toolbar).getAllByRole('button')
    expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
      '复制回答',
    ])
    expect(buttons.map((button) => (button as HTMLButtonElement).disabled)).toEqual([
      false,
    ])
    buttons.slice(1, 6).forEach((button) => fireEvent.click(button))
    expect(screen.queryByLabelText('推演证据')).toBeNull()
    expect(screen.queryByLabelText('本次执行过程')).toBeNull()
  })
  it('does not advertise unimplemented feedback actions', async () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '已读取模型。' }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByRole('button', { name: '复制回答' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '回答有帮助' })).toBeNull()
    expect(screen.queryByRole('button', { name: '回答需改进' })).toBeNull()
    expect(screen.queryByRole('button', { name: '更多回答操作' })).toBeNull()
  })
  it('selects only the grid view belonging to that answer', async () => {
    const selected = vi.fn()
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '全网潮流' }, 'attempt_flow'),
      event('attempt_completed', 2, { answer: '前三条线路' }, 'attempt_rank'),
      event('attempt_completed', 3, { answer: '目录信息' }, 'attempt_catalog'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      selectedNetworkAttempt="attempt_flow" networkAttemptIds={['attempt_flow', 'attempt_rank']} onShowNetwork={selected} />)
    const actions = await screen.findAllByRole('button', { name: '查看此指令电网图' })
    expect(actions).toHaveLength(2)
    expect((actions[0] as HTMLButtonElement).disabled).toBe(false)
    expect((actions[1] as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(actions[0])
    expect(selected).toHaveBeenLastCalledWith('attempt_flow')
    fireEvent.click(actions[1])
    expect(selected).toHaveBeenLastCalledWith('attempt_rank')
    for (const action of actions) expect(action.hasAttribute('aria-pressed')).toBe(false)
    fireEvent.click(actions[0])
    expect(selected).toHaveBeenLastCalledWith('attempt_flow')
    expect(actions[0].classList.contains('is-active')).toBe(false)
  })
  it('projects public command and harness deltas into assistant-ui messages', () => {
    const messages = projectAssistantMessages([
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '检查当前线路' } }),
      event('assistant_text_delta', 2, { text: '正在读取模型。' }, 'attempt_1'),
      event('assistant_text_delta', 3, { text: ' 已完成。' }, 'attempt_1'),
      event('attempt_completed', 4, {}, 'attempt_1'),
    ])

    expect(messages.map((message) => [message.role, message.content])).toEqual([
      ['user', '检查当前线路'], ['assistant', [{ type: 'text', text: '正在读取模型。 已完成。' }]],
    ])
    expect(messages[1].status).toEqual({ type: 'complete', reason: 'stop' })
  })

  it('renders the mainstream chat surface with the Capstone composer', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_ordinary', payload: { text: '查看当前模型' } }),
      event('assistant_text_delta', 2, { text: '当前模型为 IEEE-39。' }, 'attempt_1'),
    ]} disabled={false} isRunning={true} activity={['工具已启动 · capstone-harness']} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByTestId('assistant-ui-chat')).toBeTruthy()
    expect(screen.getByText('查看当前模型')).toBeTruthy()
    expect(screen.getByText('当前模型为 IEEE-39。')).toBeTruthy()
    expect(screen.getByText(/工具已启动/)).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Thread 指令' })).toBeTruthy()
    expect(screen.getByLabelText('输入工具栏')).toBeTruthy()
    expect(screen.getByRole('button', { name: '对话设置' })).toBeTruthy()
    expect(screen.queryByText('自动路由')).toBeNull()
    expect(screen.queryByRole('button', { name: '自动识别' })).toBeNull()
    expect(screen.queryByRole('button', { name: '专业分析' })).toBeNull()
    expect(screen.queryByText(/⌘\/Ctrl/)).toBeNull()
  })

  it('puts the cross-family model questions first in the empty-thread suggestions', () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(within(screen.getByLabelText('示例问题')).getAllByRole('button').map((button) => button.textContent)).toEqual([
      '有哪些 PyPSA 的电网模型？',
      '有哪些 pandapower 的电网模型？',
      'IEEE-39 有哪些母线和线路？',
      '对 IEEE-39 执行一次交流潮流。',
      '筛查负载率最高的三条线路。',
    ])
  })

  it('shows an explicit processing state for an assistant message without text yet', () => {
    render(<CapstoneAssistantThread events={[
      event('assistant_text_delta', 1, { text: '' }, 'attempt_1'),
    ]} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.getByText('正在生成回答…')).toBeTruthy()
  })

  it('shows tool activity and elapsed time as soon as an attempt starts', () => {
    const startedAt = new Date(Date.now() - 2300).toISOString()
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '读取当前模型' } }, 'attempt_live', startedAt),
      event('attempt_started', 2, {}, 'attempt_live', startedAt),
      event('tool_started', 3, { tool_name: 'grid_model_list', binding_id: 'grid', capability: 'model.list' }, 'attempt_live', new Date(Date.now() - 1200).toISOString()),
    ]
    const messages = projectAssistantMessages(events)
    expect(messages).toHaveLength(2)
    expect(messages[1].status).toEqual({ type: 'running' })
    expect((messages[1].metadata as { custom?: { activities?: unknown[] } }).custom?.activities).toEqual([
      expect.objectContaining({ id: 'grid_model_list', label: '读取模型目录', source: 'grid · model.list', status: 'running', startedAt: expect.any(String) }),
    ])
    render(<CapstoneAssistantThread events={events} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText((_, element) => element?.tagName === 'SPAN' && element.textContent?.includes('正在执行 1 次工具调用') === true)).toBeTruthy()
    expect(screen.getAllByText(/运行中/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('读取模型目录')).toBeTruthy()
  })

  it('keeps the final attempt duration on the completed answer', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }, 'attempt_timed', '2026-09-30T00:00:00.000Z'),
      event('attempt_started', 2, {}, 'attempt_timed', '2026-09-30T00:00:00.000Z'),
      event('attempt_completed', 3, { answer: '当前模型为 IEEE-39。' }, 'attempt_timed', '2026-09-30T00:00:02.345Z'),
    ]
    const messages = projectAssistantMessages(events)
    expect((messages[1].metadata as { custom?: { durationMs?: number } }).custom?.durationMs).toBe(2345)
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('运行 2.3s')).toBeTruthy()
  })

  it('projects the authoritative answer when the harness emits it on completion', () => {
    const messages = projectAssistantMessages([
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }),
      event('attempt_completed', 2, { answer: '当前模型为 IEEE-39。' }, 'attempt_1'),
    ])

    expect(messages.map((message) => [message.role, message.content])).toEqual([
      ['user', '查看当前模型'],
      ['assistant', [{ type: 'text', text: '当前模型为 IEEE-39。' }]],
    ])
    expect(messages[1].status).toEqual({ type: 'complete', reason: 'stop' })
  })

  it('groups tool events into readable activity steps', () => {
    expect(projectAssistantActivity([
      event('tool_started', 1, { tool_name: 'grid_model_list', capability: 'model.list', binding_id: 'grid' }, 'attempt_1'),
      event('tool_completed', 2, { tool_name: 'grid_model_list', capability: 'model.list', binding_id: 'grid' }, 'attempt_1'),
      event('tool_started', 3, { tool_name: 'grid_context_get', capability: 'context.get', binding_id: 'grid' }, 'attempt_1'),
    ])).toEqual([
      expect.objectContaining({ id: 'grid_model_list', label: '读取模型目录', source: 'grid · model.list', status: 'completed', durationMs: 0 }),
      expect.objectContaining({ id: 'grid_context_get', label: '读取模型上下文', source: 'grid · context.get', status: 'running' }),
    ])
  })

  it('renders Markdown and mainstream message actions', async () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '查看当前模型' } }, 'attempt_1'),
      event('attempt_completed', 2, { answer: '## 当前模型\n\n| 项目 | 值 |\n| --- | --- |\n| 母线 | 39 |' }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByRole('heading', { name: '当前模型' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: '当前模型' }).closest('.capstone-chat-markdown')).toBeTruthy()
    expect(screen.getByRole('cell', { name: '39' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '复制回答' })).toBeTruthy()
    expect((screen.getByRole('button', { name: '重试本次指令' }) as HTMLButtonElement).disabled).toBe(false)
    expect((screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByRole('textbox', { name: 'Thread 指令' }), { target: { value: '继续分析' } })
    expect(screen.getByRole('button', { name: '发送指令' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '编辑指令' })).toBeNull()
    expect(screen.getByRole('button', { name: '复制指令' })).toBeTruthy()
    expect((screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement).value).toBe('继续分析')
  })

  it('switches evidence and execution panels without leaving both open', () => {
    render(<CapstoneAssistantThread events={[
      event('tool_completed', 1, { tool_name: 'grid_context_open', capability: 'context.open', binding_id: 'grid' }, 'panels'),
      event('attempt_completed', 2, { answer: '已完成。', evidence_refs: ['evidence:current'], admission: { status: 'admitted' } }, 'panels'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const process = screen.getByRole('button', { name: '查看执行过程' })
    const evidence = screen.getByRole('button', { name: '查看推演证据' })
    fireEvent.click(process)
    expect(process.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(evidence)
    expect(process.getAttribute('aria-expanded')).toBe('false')
    expect(screen.getByLabelText('推演证据')).toBeTruthy()
    fireEvent.click(process)
    expect(screen.queryByLabelText('推演证据')).toBeNull()
    expect(process.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(process)
    expect(process.getAttribute('aria-expanded')).toBe('false')
  })

  it('shows evidence actions only for admitted current-run references', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行交流潮流' } }, 'attempt_1'),
      event('tool_started', 2, { tool_name: 'grid_context_open', capability: 'context.open', binding_id: 'grid' }, 'attempt_1'),
      event('tool_completed', 3, { tool_name: 'grid_context_open', capability: 'context.open', binding_id: 'grid' }, 'attempt_1'),
      event('attempt_completed', 4, { answer: '潮流已收敛。', result_refs: ['result:run_1:powerflow'], evidence_refs: ['evidence:run_1:powerflow'], admission: { status: 'admitted' } }, 'attempt_1'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByRole('button', { name: '查看推演证据' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看执行过程' })).toBeTruthy()
    expect(screen.queryByLabelText('当前运行结果引用')).toBeNull()
    expect(screen.queryByLabelText('推演证据')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看推演证据' }))
    expect(screen.getByLabelText('推演证据').textContent).toContain('evidence:run_1:powerflow')
  })

  it('keeps repeated tool calls and each conversation activity separate', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '打开模型' } }, 'attempt_1'),
      event('tool_started', 2, { tool_name: 'grid_context_open', tool_call_id: 'call_a' }, 'attempt_1'),
      event('tool_completed', 3, { tool_name: 'grid_context_open', tool_call_id: 'call_a', binding_id: 'grid', capability: 'context.open' }, 'attempt_1'),
      event('attempt_completed', 4, { answer: '已打开模型。' }, 'attempt_1'),
      event('command_accepted', 5, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_2'),
      event('tool_started', 6, { tool_name: 'grid_context_get', tool_call_id: 'call_b' }, 'attempt_2'),
      event('tool_completed', 7, { tool_name: 'grid_context_get', tool_call_id: 'call_b', binding_id: 'grid', capability: 'context.get' }, 'attempt_2'),
      event('tool_started', 8, { tool_name: 'grid_context_get', tool_call_id: 'call_c' }, 'attempt_2'),
      event('tool_completed', 9, { tool_name: 'grid_context_get', tool_call_id: 'call_c', binding_id: 'grid', capability: 'context.get' }, 'attempt_2'),
      event('attempt_completed', 10, { answer: '| 指标 | 值 |\n| --- | --- |\n| 收敛 | 是 |' }, 'attempt_2'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={projectAssistantActivity(events)} onSend={async () => {}} onCancel={async () => {}} />)
    const first = screen.getByText('已打开模型。').closest('.capstone-chat-message')!
    const second = screen.getByRole('table').closest('.capstone-chat-message')!
    expect(within(first as HTMLElement).getByText('已完成 1 次工具调用')).toBeTruthy()
    expect(within(second as HTMLElement).getByText('已完成 2 次工具调用')).toBeTruthy()
    expect(first.querySelectorAll('details')).toHaveLength(1)
    expect(second.querySelectorAll('details')).toHaveLength(1)
    fireEvent.click(within(first as HTMLElement).getByRole('button', { name: '查看执行过程' }))
    expect(first.querySelector('details')?.open).toBe(true)
    expect(second.querySelector('details')?.open).toBe(false)
  })

  it('shows up to ten latest running actions until opened and respects closing it as steps arrive', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'running_activity'),
      event('attempt_started', 2, {}, 'running_activity'),
      event('tool_started', 3, { tool_name: 'grid_context_get', tool_call_id: 'call_a' }, 'running_activity'),
    ]
    const props = { disabled: false, isRunning: true, onSend: async () => {}, onCancel: async () => {} }
    const { container, rerender } = render(<CapstoneAssistantThread {...props} events={events} activity={projectAssistantActivity(events)} />)
    const details = container.querySelector<HTMLDetailsElement>('.capstone-chat-activity-attached')!
    expect(details.open).toBe(false)
    expect(screen.getByLabelText('执行过程预览').querySelectorAll('.capstone-chat-activity-item')).toHaveLength(1)
    details.open = true
    fireEvent(details, new Event('toggle'))
    expect(details.open).toBe(true)
    expect(screen.queryByLabelText('执行过程预览')).toBeNull()
    details.open = false
    fireEvent(details, new Event('toggle'))
    const next = [...events,
      event('tool_completed', 4, { tool_name: 'grid_context_get', tool_call_id: 'call_a' }, 'running_activity'),
      event('tool_started', 5, { tool_name: 'grid_model_list', tool_call_id: 'call_b' }, 'running_activity'),
      event('tool_completed', 6, { tool_name: 'grid_model_list', tool_call_id: 'call_b' }, 'running_activity'),
      event('tool_started', 7, { tool_name: 'grid_model_dataset_query', tool_call_id: 'call_c' }, 'running_activity'),
      event('tool_completed', 8, { tool_name: 'grid_model_dataset_query', tool_call_id: 'call_c' }, 'running_activity'),
      event('tool_started', 9, { tool_name: 'grid_analysis_powerflow_ac', tool_call_id: 'call_d' }, 'running_activity'),
    ]
    rerender(<CapstoneAssistantThread {...props} events={next} activity={projectAssistantActivity(next)} />)
    expect(details.open).toBe(false)
    const preview = screen.getByLabelText('执行过程预览')
    expect(preview.querySelectorAll('.capstone-chat-activity-item')).toHaveLength(4)
    expect(preview.textContent).toContain('grid_model_list')
    expect(preview.textContent).toContain('grid_context_get')
    details.open = true
    fireEvent(details, new Event('toggle'))
    const completed = [...next, event('attempt_completed', 10, { answer: '执行完成。' }, 'running_activity')]
    rerender(<CapstoneAssistantThread {...props} isRunning={false} events={completed} activity={projectAssistantActivity(completed)} />)
    expect(details.open).toBe(true)
    expect(screen.queryByLabelText('执行过程预览')).toBeNull()
    expect(details.querySelectorAll('.capstone-chat-activity-item')).toHaveLength(4)
  })

  it('renders the admitted result card and keeps evidence behind its action', () => {
    const events = [
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '运行潮流' } }, 'attempt_cards'),
      event('attempt_completed', 2, {
        answer: '潮流已收敛。',
        result_refs: ['result:run_1:powerflow'],
        evidence_refs: ['evidence:run_1:powerflow'],
        admission: { mode: 'authority_backed', assurance: 'lineage_verified', admission_ref: 'admission:run_1' },
      }, 'attempt_cards'),
    ]
    expect((projectAssistantMessages(events)[1].metadata as { custom?: { admission?: unknown } }).custom?.admission).toEqual(expect.objectContaining({ mode: 'authority_backed' }))
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.queryByLabelText('当前运行结果引用')).toBeNull()
    expect(screen.queryByLabelText('推演证据')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看推演证据' }))
    expect(screen.getByLabelText('推演证据')).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看推演证据' })).toBeTruthy()
    expect(screen.queryByText(/admission:run_1/)).toBeNull()
  })

  it('renders a structured result projection and can focus a topology element', () => {
    const onFocusElement = vi.fn()
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_professional', payload: { text: '筛查线路' } }, 'attempt_result'),
      event('attempt_completed', 2, { answer: '已完成线路筛查。' }, 'attempt_result'),
    ]} resultProjections={[{
      resultId: 'result_projection_1', resultRef: `result:sha256:${'a'.repeat(64)}`, evidenceRefs: [`evidence:sha256:${'b'.repeat(64)}`],
      threadId: 'thr_demo', runId: 'run_demo', turnId: 'turn_1', attemptId: 'attempt_result', modelContextId: 'ctx_demo', modelId: 'ieee39', modelRevision: `revision:sha256:${'c'.repeat(64)}`,
      source: { capabilityId: 'analysis.powerflow.ac.run', domainPackId: 'pandapower-static-analysis', implementationFamily: 'pandapower' }, status: 'completed',
      summary: [{ metricId: 'total_active_loss', label: '有功损耗', value: 43.64, unit: 'MW' }],
      tables: [{ tableId: 'line_loading', title: '线路负载率', columns: [{ columnId: 'line', label: '线路' }, { columnId: 'loading_percent', label: '负载率', unit: '%' }], rows: [{ rowId: 'line:11', cells: { line: '线路 11', loading_percent: 67.15 }, elementRef: { elementKind: 'line', elementId: 'line:11' } }] }],
      elementRefs: [{ elementKind: 'line', elementId: 'line:11' }], overlay: { metric: 'loading_percent', unit: '%', sourceRef: `result:sha256:${'a'.repeat(64)}`, values: [{ elementId: 'line:11', value: 67.15 }] },
    }, {
      resultId: 'result_projection_2', resultRef: `result:sha256:${'d'.repeat(64)}`, evidenceRefs: [`evidence:sha256:${'e'.repeat(64)}`],
      threadId: 'thr_demo', runId: 'run_demo', turnId: 'turn_1', attemptId: 'attempt_result', modelContextId: 'ctx_demo', modelId: 'ieee39', modelRevision: `revision:sha256:${'c'.repeat(64)}`,
      source: { capabilityId: 'analysis.powerflow.ac.run', domainPackId: 'pandapower-static-analysis', implementationFamily: 'pandapower' }, status: 'completed',
      summary: [{ metricId: 'total_active_loss_2', label: '电压偏差', value: 0.02, unit: 'pu' }], tables: [], elementRefs: [],
    }]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onFocusElement={onFocusElement} />)

    fireEvent.click(screen.getByRole('button', { name: '查看计算结果' }))
    expect(screen.getAllByRole('region', { name: '结构化计算结果' })).toHaveLength(1)
    expect(screen.getByText('有功损耗')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '线路 11' }))
    expect(onFocusElement).toHaveBeenCalledWith(expect.objectContaining({ resultId: 'result_projection_1' }), 'line:11')
    fireEvent.click(screen.getByRole('button', { name: /结果 02.*电压偏差/ }))
    expect(screen.getByText('电压偏差')).toBeTruthy()
  })

  it('opens failure records even when the task has no admitted calculation evidence', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '分析网络' } }, 'attempt_failure_records'),
      event('tool_started', 2, { tool_call_id: 'failed_call', tool_name: 'grid_analysis_run' }, 'attempt_failure_records'),
      event('tool_completed', 3, { tool_call_id: 'failed_call', ok: false, error: { message: '计算未收敛。' } }, 'attempt_failure_records'),
      event('attempt_completed', 4, { answer: '本次计算未完成，保留失败记录。' }, 'attempt_failure_records'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const action = screen.getByRole('button', { name: '查看执行过程' })
    expect((action as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(action)
    fireEvent.click(screen.getByRole('button', { name: '放大阅读执行过程' }))
    expect(screen.getByRole('region', { name: '执行失败记录' })).toBeTruthy()
    expect(screen.queryByText('计算引用已准入。业务判断的核验范围以计算结果为准。')).toBeNull()
  })

  it('shows configuration repair guidance for a runtime configuration failure', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '有哪些 PyPSA 的电网模型？' } }, 'attempt_configuration'),
      event('attempt_failed', 2, { error_code: 'runtime_configuration_invalid' }, 'attempt_configuration'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('执行失败')).toBeTruthy()
    expect(screen.getByText(/服务的 AI 配置未就绪/)).toBeTruthy()
    expect(screen.getByText(/联系管理员检查配置，修复后再重试/)).toBeTruthy()
    expect(screen.queryByText(/能力上下文准备失败/)).toBeNull()
  })

  it('shows a terminal failure with the next action instead of a generation placeholder', () => {
    render(<CapstoneAssistantThread events={[
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed', message: '潮流求解器未收敛。' }, 'attempt_failed'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={async () => {}} />)

    expect(screen.getByText('执行失败')).toBeTruthy()
    expect(screen.getByText('潮流求解器未收敛。')).toBeTruthy()
    expect(screen.queryByText('正在生成回答…')).toBeNull()
    expect(screen.getByRole('button', { name: '重试本次指令' })).toBeTruthy()
  })

  it('retries the failed Attempt identity and disables retry while another Attempt runs', async () => {
    const onRegenerate = vi.fn().mockResolvedValue(undefined)
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '运行潮流' } }, 'attempt_failed'),
      event('attempt_failed', 2, { error_code: 'solver_failed' }, 'attempt_failed'),
    ]
    const { rerender } = render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    fireEvent.click(screen.getByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalledWith('attempt_failed', '运行潮流'))
    rerender(<CapstoneAssistantThread events={events} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    expect(screen.queryByRole('button', { name: '重试本次指令' })).toBeNull()
    expect(onRegenerate).toHaveBeenCalledTimes(1)
  })

  it('keeps interrupted retry available while hiding terminal activity when trace is off', async () => {
    const onRegenerate = vi.fn().mockResolvedValue(undefined)
    const events = [
      event('command_accepted', 1, { kind: 'send_auto', payload: { text: '继续分析' } }, 'attempt_interrupted'),
      event('tool_completed', 2, { tool_name: 'grid_context_get', capability: 'context.get', binding_id: 'grid' }, 'attempt_interrupted'),
      event('assistant_text_delta', 3, { text: '已完成部分分析。' }, 'attempt_interrupted'),
      event('attempt_interrupted', 4, {}, 'attempt_interrupted'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={true} isRunning={false} activity={[]} showActivity={false} onSend={async () => {}} onCancel={async () => {}} onRegenerate={onRegenerate} />)
    expect(screen.getByRole('button', { name: '重试本次指令' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '查看执行过程' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重试本次指令' }))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalledWith('attempt_interrupted', '继续分析'))
  })

  it('keeps partial text but makes cancellation explicit and stops incomplete tool steps', () => {
    const events = [
      event('attempt_started', 1, {}, 'attempt_cancelled'),
      event('tool_started', 2, { tool_name: 'grid_context_open', tool_call_id: 'pending_tool' }, 'attempt_cancelled'),
      event('assistant_text_delta', 3, { text: '已读取部分模型。' }, 'attempt_cancelled'),
      event('attempt_cancelled', 4, {}, 'attempt_cancelled'),
    ]
    render(<CapstoneAssistantThread events={events} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(screen.getByText('已读取部分模型。')).toBeTruthy()
    expect(screen.getByText('本次 Attempt 已取消')).toBeTruthy()
    expect(screen.getByText(/已取消 · 1 次工具调用/)).toBeTruthy()
    expect(screen.queryByText(/已完成 1 次工具调用/)).toBeNull()
  })

  it('marks an interrupted run summary with the danger state', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_started', 1, {}, 'attempt_interrupted'),
      event('tool_started', 2, { tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_interrupted'),
      event('attempt_interrupted', 3, {}, 'attempt_interrupted'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    const summary = screen.getByText(/已中断 · 1 次工具调用/)
    expect(summary.closest('details')?.classList.contains('is-interrupted')).toBe(true)
  })

  it('keeps a terminal-only interrupted replay visibly dangerous', () => {
    render(<CapstoneAssistantThread events={[
      event('tool_completed', 1, { tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_terminal_only'),
      event('attempt_interrupted', 2, {}, 'attempt_terminal_only'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    const summary = screen.getByText(/已中断 · 1 次工具调用/)
    expect(summary.closest('details')?.classList.contains('is-interrupted')).toBe(true)
  })

  it('projects tool ok=false as a failure and retains completed provenance', () => {
    const activities = projectAssistantActivity([
      event('tool_started', 1, { tool_call_id: 'call_fail', tool_name: 'grid_context_open', binding_id: 'grid', capability: 'context.open' }, 'attempt_1'),
      event('tool_completed', 2, { tool_call_id: 'call_fail', ok: false }, 'attempt_1'),
    ])
    expect(activities[0]).toMatchObject({ status: 'failed', label: '打开模型上下文', source: 'grid · context.open' })
  })

  it('does not label an old answer with the newly selected model', () => {
    const terminal = { ...event('attempt_completed', 1, { answer: '旧模型结果。', evidence_refs: ['evidence:old'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'attempt_old'), modelContextId: 'ctx_old' }
    render(<CapstoneAssistantThread events={[terminal]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      modelSummary={{ modelId: 'pypsa39', implementationFamily: 'pypsa', modelRevision: 'new_revision', contextId: 'ctx_new' }} />)
    expect(screen.queryByText(/pypsa39/)).toBeNull()
    expect(screen.queryByText(/ctx_old/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '查看推演证据' }))
    expect(screen.getByText(/ctx_old/)).toBeTruthy()
  })

  it('does not render result or evidence references without current-run admission', () => {
    render(<CapstoneAssistantThread events={[
      event('attempt_completed', 1, { answer: '未准入回答。', result_refs: ['result:unadmitted'], evidence_refs: ['evidence:unadmitted'] }, 'attempt_unadmitted'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)

    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('group', { name: '推演证据' })).toBeNull()
    expect(screen.queryByRole('button', { name: '查看推演证据' })).toBeNull()
    expect(screen.queryByLabelText('推演证据')).toBeNull()
  })

  it('carries attempt model context into a terminal result card when the terminal event omits it', () => {
    const started = { ...event('attempt_started', 1, {}, 'attempt_context'), modelContextId: 'ctx_current', selectionRevision: 'sel_4' }
    render(<CapstoneAssistantThread events={[
      started,
      event('attempt_completed', 2, { answer: '潮流已收敛。', result_refs: ['result:current'], evidence_refs: ['evidence:current'], admission: { mode: 'authority_backed', assurance: 'lineage_verified' } }, 'attempt_context'),
    ]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}}
      modelSummary={{ modelId: 'ieee39', implementationFamily: 'pandapower', modelRevision: 'revision:current', contextId: 'ctx_current' }} />)

    expect(screen.getByRole('button', { name: '查看推演证据' })).toBeTruthy()
  })

  it('allows drafting during a running attempt while keeping send unavailable', () => {
    render(<CapstoneAssistantThread events={[event('attempt_started', 1, {}, 'attempt_live')]} disabled={true} isRunning={true} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    expect(input.disabled).toBe(false)
    fireEvent.change(input, { target: { value: '下一条指令草稿' } })
    expect(input.value).toBe('下一条指令草稿')
    expect(screen.queryByRole('button', { name: '发送指令' })).toBeNull()
    expect(screen.getByRole('button', { name: '停止生成' })).toBeTruthy()
  })

  it('submits pasted multiline composer text intact', async () => {
    const onSend = vi.fn().mockResolvedValue(undefined)
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement

    fireEvent.change(input, { target: { value: '第一行\n第二行' } })
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', charCode: 13 })

    await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', '第一行\n第二行', expect.objectContaining({deep_research:false})))
  })

  it('keeps a stable composer action footprint while the input is empty', async () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement
    const send = screen.getByRole('button', { name: '发送指令' }) as HTMLButtonElement

    expect(send.disabled).toBe(true)
    fireEvent.change(input, { target: { value: '查看当前模型' } })
    expect(send.disabled).toBe(false)
  })

  it('keeps the composer input focused when the Thread is ready for input', () => {
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={async () => {}} onCancel={async () => {}} />)
    expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Thread 指令' }))
  })

  it('sends multiline text from the composer action', async () => {
    const onSend = vi.fn().mockResolvedValue(undefined)
    render(<CapstoneAssistantThread events={[]} disabled={false} isRunning={false} activity={[]} onSend={onSend} onCancel={async () => {}} />)
    const input = screen.getByRole('textbox', { name: 'Thread 指令' }) as HTMLTextAreaElement

    fireEvent.change(input, { target: { value: '第一行\n第二行' } })
    fireEvent.click(screen.getByRole('button', { name: '发送指令' }))

    await waitFor(() => expect(onSend).toHaveBeenCalledWith('automatic', '第一行\n第二行', expect.objectContaining({deep_research:false})))
  })
})
