import {expect,it} from 'vitest'
import {projectProcessModelRequests} from './processModelRequests'
import {modelCallMs} from './ProcessCallTrace'
import type {EventEnvelope} from './threadProtocol'

const boundary=(seq:number,phase:string,responseKind?:string):EventEnvelope=>({eventId:`e${seq}`,eventSeq:seq,eventVersion:1,eventType:'runtime_action',threadId:'thread',runId:'run',attemptId:'attempt',visibility:'public',occurredAt:`2026-10-25T12:00:0${seq}Z`,payload:{phase,...(responseKind?{response_kind:responseKind}:{})}})
it('binds main dispatch by authoritative SDK turn and excludes queue age from parent timing',()=>{
 const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
 const record=(id:string,turn:number,extra:Record<string,unknown>={}):EventEnvelope=>({...boundary(3,id),eventType:'runtime_event',payload:{native_type:'model_request_pool',model_request_pool:{type:'model_request_pool',schema:'capstone-model-request-pool/1',request_id:id,chain_id:'main',kind:'main',model_turn_number:turn,status:'queued',depends_on:[],queued_at_ms:100,...extra}}})
 const [waiting]=projectProcessModelRequests([native,boundary(1,'started'),record('request-1',1)],'attempt')
 expect(modelCallMs(waiting,900)).toBe(0)
 const calls=projectProcessModelRequests([native,boundary(1,'started'),record('request-1',1,{status:'failed',started_at_ms:800,finished_at_ms:900}),record('request-2',1,{status:'completed',started_at_ms:950,finished_at_ms:1000}),record('request-3',99)],'attempt')
 expect(modelCallMs(calls[0],3000)).toBe(150)
 expect(calls[0].requestPool?.find(request=>request.id==='request-3')?.association).toBe('unassociated')
 expect(calls[0].stopReason).toBeUndefined()
})
it('associates analysis requests by exact parent tool and child and retains unmatched requests separately',()=>{
 const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
 const submit={...boundary(3,'tool'),eventType:'runtime_event',payload:{native_type:'tool_execution_start',tool_call_id:'submit',tool_name:'agent_llm_submit'}}
 const child={...boundary(4,'child'),eventType:'runtime_event',payload:{native_type:'llm_pool_call',llm_pool_call:{type:'llm_pool_call',schema:'capstone-llm-call-pool/1',parent_tool_call_id:'submit',child_id:'child',title:'检查',status:'running',queued_at_ms:100,started_at_ms:200}}}
 const request=(id:string,childId:string):EventEnvelope=>({...boundary(5,id),eventType:'runtime_event',payload:{native_type:'model_request_pool',model_request_pool:{type:'model_request_pool',schema:'capstone-model-request-pool/1',request_id:id,chain_id:`analysis:${childId}`,kind:'analysis',parent_tool_call_id:'submit',child_id:childId,model_turn_number:1,status:'running',depends_on:[],queued_at_ms:100,started_at_ms:200}}})
 const [call]=projectProcessModelRequests([native,boundary(1,'started'),boundary(2,'response_completed','tools'),submit,child,request('request-2','child'),request('request-3','other')],'attempt')
 expect(call.requestPool?.map(row=>row.association)).toEqual(['analysis','unassociated'])
})
it('attaches pool calls through exact submit ownership without moving them into a subsequent parent request',()=>{
 const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
 const submit={...boundary(3,'tool'),eventType:'runtime_event',payload:{native_type:'tool_execution_start',tool_call_id:'submit',tool_name:'agent_llm_submit'}}
 const child={...boundary(7,'child'),eventType:'runtime_event',payload:{native_type:'llm_pool_call',llm_pool_call:{type:'llm_pool_call',schema:'capstone-llm-call-pool/1',parent_tool_call_id:'submit',child_id:'child',title:'检查',status:'running',queued_at_ms:1,started_at_ms:2}}}
 const calls=projectProcessModelRequests([native,boundary(1,'started'),boundary(2,'response_completed','tools'),submit,boundary(4,'started'),boundary(5,'response_completed','text'),child],'attempt')
 expect(calls[0].poolCalls?.[0].id).toBe('child');expect(calls[1].poolCalls).toBeUndefined()
 const [unbound]=projectProcessModelRequests([native,submit,boundary(4,'started'),boundary(5,'response_completed','text'),child],'attempt')
 expect(unbound.poolCalls).toBeUndefined()
})

it('distinguishes a recorded text-only response from missing tool ownership metadata',()=>{
  const calls=projectProcessModelRequests([boundary(1,'started'),boundary(2,'response_completed','text'),boundary(3,'started'),boundary(4,'response_completed','tools')],'attempt')
  expect(calls[0].toolCallIds).toEqual([])
  expect(calls[1].toolCallIds).toBeUndefined()
})
it('retains safe model error classification on the failed request',()=>{
  const end=boundary(2,'response_completed','error');end.payload.error_code='model_context_limit';end.payload.error_status=400
  const [call]=projectProcessModelRequests([boundary(1,'started'),end],'attempt')
  expect(call.errorCode).toBe('model_context_limit')
  expect(call.errorStatus).toBe(400)
})
it('uses only the response first-line action comment and keeps reasoning out of the call purpose',()=>{
  const delta=(seq:number,type:string,text:string):EventEnvelope=>({...boundary(seq,'delta'),eventType:type,visibility:'diagnostic',payload:{text}})
  const calls=projectProcessModelRequests([boundary(1,'started'),delta(2,'assistant_thinking_delta','// PRIVATE reasoning'),delta(3,'assistant_process_delta','// 核对'),delta(4,'assistant_process_delta','指标口径\n实际回复\n// later text'),boundary(5,'response_completed','tools'),boundary(6,'completed'),boundary(7,'started')],'attempt')
  expect(calls[0].intent).toBe('核对指标口径')
  expect(calls[1].intent).toBeUndefined()
})
it('keeps public thinking within its actual request and does not aggregate later rounds',()=>{
  const thought=(seq:number,text:string):EventEnvelope=>({...boundary(seq,'thought'),eventType:'assistant_thinking_delta',payload:{text}})
  const first=thought(2,'First thought. ')
  const calls=projectProcessModelRequests([boundary(1,'started'),first,first,boundary(3,'response_completed','tools'),thought(4,'Outside response.'),boundary(5,'completed'),boundary(6,'started'),thought(7,'Second thought.')],'attempt')
  expect(calls[0].thinking).toBe('First thought. ')
  expect(calls[1].thinking).toBe('Second thought.')
})
it('binds observed native tools through explicit SDK turn boundaries, never just adjacent times',()=>{
  const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
  const tool=(seq:number,id:string):EventEnvelope=>({...boundary(seq,'tool'),eventType:'runtime_event',payload:{native_type:'tool_execution_start',tool_call_id:id,tool_name:'read'}})
  const calls=projectProcessModelRequests([native,tool(0,'outside'),boundary(1,'started'),boundary(2,'response_completed','tools'),tool(3,'first'),tool(3,'first'),boundary(4,'completed'),tool(4,'after'),boundary(5,'started'),boundary(6,'response_completed','text'),boundary(7,'completed')],'attempt')
  expect(calls.map(call=>call.toolCallIds)).toEqual([['first'],[]])
  expect(calls[0].toolAssociation).toBe('turn')
  const [legacy]=projectProcessModelRequests([boundary(1,'started'),boundary(2,'response_completed','tools'),tool(3,'unbound')],'attempt')
  expect(legacy.toolCallIds).toBeUndefined()
})
it('keeps a missing response incomplete when a new explicit turn starts',()=>{
  const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
  const tool={...boundary(5,'tool'),eventType:'runtime_event',payload:{native_type:'tool_execution_start',tool_call_id:'second-tool',tool_name:'read'}}
  const calls=projectProcessModelRequests([native,boundary(1,'started'),boundary(2,'started'),boundary(4,'response_completed','tools'),tool],'attempt')
  expect(calls).toHaveLength(2)
  expect(calls[0].finishedAt).toBeUndefined();expect(calls[0].settled).toBe(true)
  expect(calls[1].ms).toBe(2000);expect(calls[1].toolCallIds).toEqual(['second-tool'])
})
it('does not bind a tool to the old turn after an unmatched response boundary',()=>{
  const native={...boundary(0,'route'),eventType:'turn_route_selected',payload:{source:'native_conversation'}}
  const tool={...boundary(5,'tool'),eventType:'runtime_event',payload:{native_type:'tool_execution_start',tool_call_id:'unbound',tool_name:'read'}}
  const [call]=projectProcessModelRequests([native,boundary(1,'started'),boundary(2,'response_completed','tools'),boundary(4,'response_completed','tools'),tool],'attempt')
  expect(call.toolCallIds).toEqual([])
})
