import {expect,it} from 'vitest'
import type {EventEnvelope} from './threadProtocol'
import {projectInstructionContexts} from './instructionContext'

it('keeps explicit requests and compaction with the right retry and omits private observations',()=>{
  const event=(eventSeq:number,attemptId:string,turnId:string,payload:Record<string,unknown>,visibility='public')=>({
    eventSeq,eventId:'evt_'+eventSeq,attemptId,turnId,visibility,eventType:'runtime_event',payload,
  }) as EventEnvelope
  const start={request_id:'ctx-1',kind:'main',state:'started',window_tokens:10000,estimated_input:{system:1000,tools:200}}
  const events=[
    event(2,'one','turn-a',{model_context_usage:start}),
    event(3,'one','turn-a',{model_context_usage:{...start,state:'completed',usage:{input:100,cacheRead:1000,cacheWrite:100,output:35}}}),
    event(4,'one','turn-a',{native_type:'runtime_phase',runtime_phase:{name:'context_compaction',state:'completed',reason:'threshold',tokens_before:9000}}),
    event(5,'two','turn-a',{model_context_usage:start}),
    event(6,'two','turn-a',{model_context_usage:{...start,state:'completed',usage:{input:600,output:10}}}),
    event(7,'other','turn-b',{model_context_usage:start}),
    event(8,'other','turn-b',{model_context_usage:{...start,request_id:'ctx-2'}},'diagnostic'),
  ]
  const rows=projectInstructionContexts(events)
  expect(rows.filter(row=>row.instructionId==='turn-a').map(row=>[row.attemptId,row.kind,row.inputTokens])).toEqual([
    ['one','main',1200],['one','compaction',9000],['two','main',1200],
  ])
  expect(rows[2].basis).toBe('estimate')
  expect(rows).toHaveLength(4)
})
