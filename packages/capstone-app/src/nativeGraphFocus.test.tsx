import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import {parseEventEnvelope,type EventEnvelope} from './threadProtocol'
import toolsFixture from './fixtures/nativeGraph-tools.json'
import researchFixture from './fixtures/nativeGraph-research.json'
import resourceScope from './fixtures/nativeGraph-resource-scope.json'

afterEach(()=>{cleanup();localStorage.clear()})
// Structural excerpts from real same-Work Attempts; all free text/output is synthetic.
const tools=toolsFixture.map(parseEventEnvelope),research=researchFixture.map(parseEventEnvelope)
const props={disabled:false,isRunning:false,activity:[],onSend:async()=>{},onCancel:async()=>{}}
function read(events:EventEnvelope[]) {
  expect(projectAssistantMessages(events).at(-1)?.metadata?.custom?.executionGraph).toBeTruthy()
  render(<CapstoneAssistantThread {...props} events={events} />)
  fireEvent.click(screen.getByRole('button',{name:'放大阅读执行过程'}))
  return within(screen.getByRole('dialog',{name:'执行过程'}))
}
it('shows actual admitted child tools as primary even when native organization used a graph',()=>{
  const reader=read(tools)
  const chain=within(reader.getByRole('region',{name:'工具调用过程'}))
  expect(chain.getAllByText('bash',{selector:'strong'})).toHaveLength(1)
  expect(chain.getByText('0.0s',{selector:'.capstone-call-duration'})).toBeTruthy()
  expect(reader.getByText('任务组织记录').closest('details')?.open).toBe(false)
  expect(screen.queryByText(/1 个任务步骤/)).toBeNull()
})
it('changes to business planning on admitted registered data tools in the next Attempt of the same Work',()=>{
  const reader=read(research)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('changes live focus only after the current graph admits business tool execution and replays the same view',()=>{
  const firstActivity=research.find(event=>event.payload.research_graph_event&&typeof event.payload.research_graph_event==='object'&&'activity' in event.payload.research_graph_event)!
  const before=research.filter(event=>event.eventSeq<firstActivity.eventSeq)
  const {rerender,unmount}=render(<CapstoneAssistantThread {...props} isRunning events={before}/>)
  expect(screen.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  rerender(<CapstoneAssistantThread {...props} isRunning events={research.filter(event=>event.eventType!=='attempt_completed')}/>)
  expect(screen.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(screen.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
  unmount()
  const reader=read(research)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('preserves uploaded-material business plans and historical graph presentation',()=>{
  const selected=tools.map(event=>event.eventType==='turn_plan_created'?{...event,payload:{...event.payload,accepted_context:{objects:[],materials:[{material_id:`material_${'a'.repeat(32)}`}],full_model_tables:false}}}:event)
  let reader=read(selected)
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
  cleanup()
  reader=read(tools.filter(event=>event.eventType!=='turn_plan_created'))
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('does not promote arbitrary unbound business-like tool names to a business plan',()=>{
  const raw={...tools[0],eventId:'unbound',eventSeq:tools.at(-1)!.eventSeq+1,eventType:'runtime_event',payload:{native_type:'tool_execution_end',task_id:'task',tool_call_id:'unbound',tool_name:'data_gateway_invented'}}
  const reader=read([...tools,raw])
  expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
  expect(reader.getByText('任务组织记录').closest('details')?.open).toBe(false)
})
function resourceGraphEvents(revision=resourceScope.source_versions[0].revision) {
  return tools.map(event=>{
    const progress=event.payload.research_graph as {graph?:{nodes:Record<string,unknown>[];actions:Record<string,unknown>[]}}|undefined
    if(!progress?.graph)return event
    const versions=resourceScope.source_versions.map(source=>({...source,revision}))
    return {...event,payload:{...event.payload,research_graph:{...progress,graph:{...progress.graph,
      nodes:progress.graph.nodes.map(node=>({...node,source_refs:resourceScope.source_refs,selected_source_versions:versions})),
      actions:progress.graph.actions.map(action=>({...action,source_refs:resourceScope.source_refs,source_versions:versions})),
    }}}}
  })
}
it('keeps uploaded business research task steps primary from admitted frozen graph resource versions with empty Work grants',()=>{
  const reader=read(resourceGraphEvents())
  expect(reader.queryByRole('region',{name:'工具调用过程'})).toBeNull()
  expect(reader.getByRole('button',{name:'查看完整计划'})).toBeTruthy()
})
it('requires the exact resource content hash instead of an arbitrary graph source label or mismatched version',()=>{
  const reader=read(resourceGraphEvents(`sha256:${'c'.repeat(64)}`))
  expect(reader.getByRole('region',{name:'工具调用过程'})).toBeTruthy()
})
