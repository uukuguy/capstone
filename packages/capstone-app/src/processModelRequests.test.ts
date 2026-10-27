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
