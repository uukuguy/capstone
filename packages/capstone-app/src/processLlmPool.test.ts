import {expect,it} from 'vitest'
import {projectLlmPoolCalls} from './processLlmPool'
import type {EventEnvelope} from './threadProtocol'
const frame=(seq:number,status:string,extra:Record<string,unknown>={}):EventEnvelope=>({eventId:`pool-${seq}`,eventSeq:seq,eventVersion:1,eventType:'runtime_event',threadId:'thread',runId:'run',attemptId:'a',visibility:'public',occurredAt:'2026-10-29T00:00:00Z',payload:{native_type:'llm_pool_call',llm_pool_call:{type:'llm_pool_call',schema:'capstone-llm-call-pool/1',parent_tool_call_id:'submit',child_id:'child',title:'核对口径',status,queued_at_ms:100,...extra}}})
const submit:EventEnvelope={...frame(0,'queued'),payload:{native_type:'tool_execution_start',tool_call_id:'submit',tool_name:'agent_llm_submit'}}
it('retains actual response timings across terminal updates and replay without counting queue time',()=>{
 const response=frame(3,'running',{started_at_ms:200,response_number:1,response_ms:45})
 const calls=projectLlmPoolCalls([submit,frame(1,'queued'),frame(2,'running',{started_at_ms:200}),response,response,frame(4,'completed',{started_at_ms:200,finished_at_ms:900,model_responses:1})],'a')
 expect(calls).toEqual([expect.objectContaining({id:'child',parentToolCallId:'submit',status:'completed',responseMs:45,responseCount:1})])
})
it('excludes private, foreign-attempt, unbound and malformed pool events',()=>{
 expect(projectLlmPoolCalls([frame(1,'queued')],'a')).toEqual([])
 expect(projectLlmPoolCalls([submit,{...frame(2,'queued'),visibility:'diagnostic'},{...frame(3,'queued'),attemptId:'b'},frame(4,'invented')],'a')).toEqual([])
})
it('keeps response time unknown when only terminal usage count was supplied',()=>{
 const [call]=projectLlmPoolCalls([submit,frame(1,'queued'),frame(2,'failed',{model_responses:1,finished_at_ms:900})],'a')
 expect(call.responseCount).toBe(1);expect(call.responseMs).toBeUndefined()
})
it('does not claim complete cumulative timing when one of the actual responses is missing',()=>{
 const [call]=projectLlmPoolCalls([submit,frame(1,'running',{started_at_ms:200,response_number:1,response_ms:45}),frame(2,'completed',{started_at_ms:200,finished_at_ms:900,model_responses:2})],'a')
 expect(call.responseCount).toBe(2);expect(call.responseMs).toBeUndefined()
})
