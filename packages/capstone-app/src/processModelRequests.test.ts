import {expect,it} from 'vitest'
import {projectProcessModelRequests} from './processModelRequests'
import type {EventEnvelope} from './threadProtocol'

const boundary=(seq:number,phase:string,responseKind?:string):EventEnvelope=>({eventId:`e${seq}`,eventSeq:seq,eventVersion:1,eventType:'runtime_action',threadId:'thread',runId:'run',attemptId:'attempt',visibility:'public',occurredAt:`2026-10-25T12:00:0${seq}Z`,payload:{phase,...(responseKind?{response_kind:responseKind}:{})}})

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
