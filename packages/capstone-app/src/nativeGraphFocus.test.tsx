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
  expect(screen.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
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
