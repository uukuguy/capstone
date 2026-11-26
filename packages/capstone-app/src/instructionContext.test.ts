import {expect,it} from 'vitest'
import type {EventEnvelope} from './threadProtocol'
import {contextToolExcerpt,projectInstructionContexts} from './instructionContext'

it('keeps explicit requests and compaction with the right retry and omits private observations',()=>{
  const event=(eventSeq:number,attemptId:string,turnId:string,payload:Record<string,unknown>,visibility='public')=>({
    eventSeq,eventId:'evt_'+eventSeq,attemptId,turnId,visibility,eventType:'runtime_event',payload,
  }) as EventEnvelope
  const start={request_id:'ctx-1',dispatch_id:'request-71',kind:'main',state:'started',window_tokens:10000,input_ceiling_tokens:8000,estimated_input:{system:1000,tools:200,tool_results:0},estimated_input_before_projection:{tool_results:180}}
  const events=[
    event(2,'one','turn-a',{model_context_usage:start}),
    event(3,'one','turn-a',{model_context_usage:{...start,state:'completed',usage:{input:100,cacheRead:1000,cacheWrite:100,output:35}}}),
    event(4,'one','turn-a',{native_type:'runtime_phase',runtime_phase:{name:'context_compaction',state:'completed',reason:'threshold',tokens_before:9000}}),
    event(5,'two','turn-a',{model_context_usage:start}),
    event(6,'two','turn-a',{model_context_usage:{...start,state:'completed',usage:{input:600,output:10}}}),
    event(7,'other','turn-b',{model_context_usage:{...start,estimated_input:{system:7000,tools:1500}}}),
    event(8,'other','turn-b',{model_context_usage:{...start,request_id:'ctx-2'}},'diagnostic'),
  ]
  const rows=projectInstructionContexts(events)
  expect(rows.filter(row=>row.instructionId==='turn-a').map(row=>[row.attemptId,row.kind,row.inputTokens])).toEqual([
    ['one','main',1200],['one','compaction',9000],['two','main',1200],
  ])
  expect(rows[2].basis).toBe('estimate')
  expect(rows).toHaveLength(4)
  expect(rows[0].dispatchId).toBe('request-71')
  expect(rows[0].inputCeilingTokens).toBe(8000)
  expect(rows[0].estimatedProjectionSavings).toBe(180)
  expect(rows.find(row=>row.instructionId==='turn-b')?.estimatedAboveCeiling).toBe(500)
})

it('reads an exact saved tool excerpt, without exposing private or ambiguous events',()=>{
  const item={eventId:'evt_tool',eventSeq:1,eventVersion:1,threadId:'thread-a',runId:'run-a',turnId:'turn-a',occurredAt:'2026-11-22T00:00:00Z',eventType:'runtime_event',attemptId:'attempt-a',visibility:'public',payload:{
    native_type:'tool_execution_end',tool_call_id:'call_1',activity:{output_excerpt:'Saved file contents'},
  }} satisfies EventEnvelope
  expect(contextToolExcerpt([item],'call_1','attempt-a')).toBe('Saved file contents')
  expect(contextToolExcerpt([{...item,payload:{...item.payload,activity:{output_excerpt:'api_key: example'}}}],'call_1','attempt-a'))
    .toBe('输出包含受保护配置或凭据信息，已隐藏。')
  expect(contextToolExcerpt([{...item,visibility:'diagnostic'}],'call_1','attempt-a')).toBeUndefined()
  expect(contextToolExcerpt([item,{...item,attemptId:'attempt-b'}],'call_1','other')).toBeUndefined()
})
