import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import {parseEventEnvelope,type EventEnvelope} from './threadProtocol'
import toolsFixture from './fixtures/nativeGraph-tools.json'
import researchFixture from './fixtures/nativeGraph-research.json'
import resourceScope from './fixtures/nativeGraph-resource-scope.json'

afterEach(()=>{cleanup();localStorage.clear()})
const tools=toolsFixture.map(parseEventEnvelope),research=researchFixture.map(parseEventEnvelope)
const props={disabled:false,isRunning:false,activity:[],onSend:async()=>{},onCancel:async()=>{}}
function read(events:EventEnvelope[]) {
  render(<CapstoneAssistantThread {...props} events={events} />)
  fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
  return within(screen.getByRole('dialog',{name:'执行过程'}))
}
it('shows actual task organization as primary without uploaded resources or business tool names',()=>{
  expect(projectAssistantMessages(tools).at(-1)?.metadata?.custom?.executionGraph).toBeTruthy()
  const reader=read(tools)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
  expect(screen.getByText(/1 个任务步骤/)).toBeTruthy()
})
it('shows registered research task organization in the next Attempt of the same Work',()=>{
  const reader=read(research)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('hands thinking over when the actual plan checkpoint is admitted, before child tools',()=>{
  const checkpoint=research.find(event=>event.payload.research_graph)!
  const {rerender}=render(<CapstoneAssistantThread {...props} isRunning events={research.filter(event=>event.eventSeq<checkpoint.eventSeq)}/>)
  expect(screen.getByRole('region',{name:'思考状态'})).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} isRunning events={research.filter(event=>event.eventSeq<=checkpoint.eventSeq)}/>)
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
  expect(within(screen.getByRole('dialog',{name:'执行过程'})).getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('keeps uploaded research task steps primary from admitted organization with empty Work grants',()=>{
  const selected=tools.map(event=>{
    const progress=event.payload.research_graph as {graph?:{nodes:Record<string,unknown>[];actions:Record<string,unknown>[]}}|undefined
    if(!progress?.graph)return event
    return {...event,payload:{...event.payload,research_graph:{...progress,graph:{...progress.graph,
      nodes:progress.graph.nodes.map(node=>({...node,source_refs:resourceScope.source_refs,selected_source_versions:resourceScope.source_versions})),
      actions:progress.graph.actions.map(action=>({...action,source_refs:resourceScope.source_refs,source_versions:resourceScope.source_versions})),
    }}}}
  })
  const reader=read(selected)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
const plainTools=()=>[
  tools[0],
  {...tools[0],eventId:'plain-read',eventSeq:tools[0].eventSeq+1,eventType:'runtime_event',payload:{native_type:'tool_execution_start',task_id:'task',tool_call_id:'read-one',tool_name:'read'}},
  {...tools[0],eventId:'plain-bash',eventSeq:tools[0].eventSeq+2,eventType:'runtime_event',payload:{native_type:'tool_execution_end',task_id:'task',tool_call_id:'bash-two',tool_name:'bash'}},
]
it('keeps lightweight narrative progress in the tool chain without claiming DR task organization',()=>{
  const events=[...plainTools(),{...tools[0],eventId:'native-route',eventSeq:998,eventType:'turn_route_selected',payload:{source:'native_conversation',route:'ordinary'}},
    {...tools[0],eventId:'narrative-progress',eventSeq:999,eventType:'runtime_event',payload:{native_type:'tool_execution_end',task_id:'task',tool_name:'agent_task_progress',tool_call_id:'progress',task_progress:{kind:'goal',phase:'started',step_id:'recon',text:'核查资料'},task_step:{id:'native.recon',number:2,title:'核查资料',status:'running'}}}]
  const reader=read(events)
  expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  expect(screen.queryByText(/1 个任务步骤/)).toBeNull()
  expect(reader.getByText(/3 次工具调用/)).toBeTruthy()
})
it('shows lightweight LLM durations and counts with collapsed tools under the owning response',()=>{
  const seed=tools[0]
  const ev=(seq:number,type:string,payload:Record<string,unknown>):EventEnvelope=>({...seed,eventId:`timing-${seq}`,eventSeq:seq,eventType:type,occurredAt:`2026-10-29T00:00:0${seq}Z`,payload})
  const events=[seed,ev(1,'turn_route_selected',{source:'native_conversation'}),ev(2,'runtime_action',{phase:'started'}),
    ev(4,'runtime_action',{phase:'response_completed',response_kind:'tools'}),
    ev(5,'runtime_event',{native_type:'tool_execution_start',task_id:'task',tool_call_id:'read-timed',tool_name:'read'}),
    ev(6,'runtime_event',{native_type:'tool_execution_end',task_id:'task',tool_call_id:'read-timed',tool_name:'read',activity:{operation:'source.csv',output_excerpt:'Exact source output'}}),
    ev(7,'runtime_action',{phase:'completed'})]
  const reader=read(events)
  const model=reader.getByRole('group',{name:'LLM 调用 1'})
  expect(within(model).getByText('2.0s')).toBeTruthy()
  const detail=model.querySelector('details.capstone-call-tool')!
  expect(detail).toBeTruthy();expect(detail.hasAttribute('open')).toBe(true)
  fireEvent.click(reader.getByRole('button',{name:'折叠工具详情'}))
  expect(detail.hasAttribute('open')).toBe(false)
  fireEvent.click(reader.getByRole('button',{name:'展开工具详情'}))
  expect(detail.hasAttribute('open')).toBe(true)
  expect(detail.querySelector('summary')?.textContent).toContain('1.0s')
  expect(reader.getByText(/LLM 1 次 · 累计 2.0s/)).toBeTruthy()
  expect(reader.getByText(/1 次工具调用/)).toBeTruthy()
})
it('shows actual tool chains without organization as tools, regardless of accepted materials',()=>{
  const events=[...plainTools(),{...tools[1],eventId:'materials',payload:{...tools[1].payload,accepted_context:{objects:[],materials:[{material_id:`material_${'a'.repeat(32)}`}]}}}]
  expect(projectAssistantMessages(events).at(-1)?.metadata?.custom?.executionGraph).toBeUndefined()
  const reader=read(events)
  expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  expect(reader.queryByRole('button',{name:'查看完整计划'})).toBeNull()
})
it('does not treat an unadmitted graph or arbitrary business-like tool name as organization',()=>{
  const invalid=tools.find(event=>event.payload.research_graph)!
  const progress=invalid.payload.research_graph as Record<string,unknown>
  const events=[...plainTools(),{...invalid,payload:{...invalid.payload,research_graph:{...progress,owner:{thread_id:'wrong-owner'}}}},
    {...tools[0],eventId:'unbound',eventSeq:999,eventType:'runtime_event',payload:{native_type:'tool_execution_end',task_id:'task',tool_call_id:'unbound',tool_name:'data_gateway_invented'}}]
  expect(projectAssistantMessages(events).at(-1)?.metadata?.custom?.executionGraph).toBeUndefined()
  const reader=read(events)
  expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  expect(reader.queryByRole('button',{name:'查看完整计划'})).toBeNull()
})
it('retains lightweight thinking and tool records exactly once when an admitted plan arrives',()=>{
  const seed=tools[0]
  const thought={...seed,eventId:'light-thought',eventSeq:seed.eventSeq+1,eventType:'assistant_thinking_delta',payload:{text:'Before the plan. '}}
  const read={...seed,eventId:'light-read',eventSeq:seed.eventSeq+2,eventType:'runtime_event',payload:{native_type:'tool_execution_end',task_id:'light-task',tool_call_id:'light-read',tool_name:'read',activity:{operation:'Read before planning'}}}
  const next={...seed,eventId:'light-next',eventSeq:seed.eventSeq+3,eventType:'assistant_thinking_delta',payload:{text:'Now organize the work.'}}
  const before=[seed,thought,read,next]
  const {rerender}=render(<CapstoneAssistantThread {...props} isRunning events={before}/>)
  expect(screen.getByRole('region',{name:'初始思考记录'})).toBeTruthy()
  expect(screen.queryByRole('region',{name:'思考状态'})).toBeNull()
  expect(screen.getAllByText('Read before planning')).toHaveLength(1)
  const events=[...before,...tools.slice(1).map(event=>({...event,eventSeq:event.eventSeq+10}))]
  rerender(<CapstoneAssistantThread {...props} events={events}/>)
  const archive=screen.getByRole('region',{name:'初始思考记录'})
  expect(within(archive).getByRole('button',{name:'展开初始思考'})).toBeTruthy()
  const projected=projectAssistantMessages(events).at(-1)?.metadata?.custom
  expect((projected?.initialThinking as {text:string}).text).toBe('Before the plan. ')
  expect((projected?.initialThinking as {continuationText:string}).continuationText).toBe('Now organize the work.')
  expect(projected?.executionGraph).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
  const reader=within(screen.getByRole('dialog',{name:'执行过程'}))
  // The full-round timing view also references this call. It remains one
  // activity record in the process, not a second execution.
  const activities=screen.getByRole('dialog',{name:'执行过程'}).querySelectorAll('.capstone-chat-activity-item')
  expect([...activities].filter(item=>item.textContent?.includes('Read before planning'))).toHaveLength(1)
  expect((projected?.activities as {operation?:string}[]).filter(item=>item.operation==='Read before planning')).toHaveLength(1)
  expect(reader.getAllByText('Before the plan.')).toHaveLength(1)
  expect(reader.getAllByText('Now organize the work.')).toHaveLength(1)
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
