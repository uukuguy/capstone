import {expect,it} from 'vitest'
import {projectModelRequestPool,requestExecutionMs,summarizeModelRequestPool} from './processModelRequestPool'
import type {EventEnvelope} from './threadProtocol'
const event=(status:string,extra:Record<string,unknown>={}):EventEnvelope=>({eventId:`${status}-${JSON.stringify(extra)}`,eventSeq:1,eventVersion:1,eventType:'runtime_event',threadId:'thread',runId:'run',attemptId:'a',visibility:'public',occurredAt:'2026-10-29T00:00:00Z',payload:{native_type:'model_request_pool',model_request_pool:{type:'model_request_pool',schema:'capstone-model-request-pool/1',request_id:'request-1',chain_id:'main',kind:'main',model_turn_number:1,depends_on:[],queued_at_ms:100,status,...extra}}})
it('measures actual dispatch execution rather than queue age and folds replay into one request',()=>{
 const queued=event('queued');const [pending]=projectModelRequestPool([queued,queued],'a')
 expect(requestExecutionMs(pending,900)).toBeUndefined()
 const [running]=projectModelRequestPool([queued,event('running',{started_at_ms:800})],'a')
 expect(requestExecutionMs(running,900)).toBe(100)
 const [done]=projectModelRequestPool([queued,event('completed',{started_at_ms:800,finished_at_ms:950})],'a')
 expect(requestExecutionMs(done,2000)).toBe(150)
})
it('ignores private/foreign/malformed records without inventing association',()=>{
 expect(projectModelRequestPool([{...event('queued'),visibility:'diagnostic'},{...event('queued'),attemptId:'other'},event('invented')],'a')).toEqual([])
 const [unknown]=projectModelRequestPool([event('queued',{model_turn_number:undefined})],'a')
 expect(unknown.modelTurnNumber).toBeUndefined()
})
it('counts cancelling as reserved and reports actual main/analysis overlap only',()=>{
 const rows=projectModelRequestPool([event('completed',{started_at_ms:200,finished_at_ms:400}),event('completed',{request_id:'request-2',chain_id:'analysis:x',kind:'analysis',child_id:'x',parent_tool_call_id:'submit',started_at_ms:300,finished_at_ms:500}),event('waiting_dependencies',{request_id:'request-3',depends_on:['request-2']}),event('cancelling',{request_id:'request-4',started_at_ms:450})],'a')
 const summary=summarizeModelRequestPool(rows,600)
 expect(summary.started).toBe(3);expect(summary.queued).toBe(1);expect(summary.reserved).toBe(1);expect(summary.maxConcurrency).toBe(2)
})
