import type {EventEnvelope} from './threadProtocol'
export type RequestStatus='queued'|'waiting_dependencies'|'running'|'cancelling'|'completed'|'failed'|'cancelled'|'blocked'
export type ProcessModelRequest={id:string;chainId:string;kind:'main'|'analysis';modelTurnNumber?:number;title?:string;dependsOn:string[];status:RequestStatus;queuedAtMs:number;startedAtMs?:number;finishedAtMs?:number;parentToolCallId?:string;childId?:string;association?:'main'|'analysis'|'unassociated'}
 & {firstContentAtMs?:number;cancelRequestedAtMs?:number;settlementUnobserved?:boolean}
const statuses=new Set(['queued','waiting_dependencies','running','cancelling','completed','failed','cancelled','blocked'])
const settled=new Set(['completed','failed','cancelled','blocked'])
const attemptTerminals=new Set(['attempt_completed','attempt_failed','attempt_cancelled','attempt_interrupted'])
const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
const text=(value:unknown):value is string=>typeof value==='string'&&value.length>0&&value.length<=128&&!/[\x00-\x1f\x7f]/.test(value)
export function projectModelRequestPool(events:readonly EventEnvelope[],attemptId:string):ProcessModelRequest[]{
 const requests=new Map<string,ProcessModelRequest>()
 let attemptEnded=false
 for(const event of events){
  if(event.attemptId!==attemptId||event.visibility!=='public')continue
  if(attemptTerminals.has(event.eventType))attemptEnded=true
  if(event.eventType!=='runtime_event'||event.payload.native_type!=='model_request_pool')continue
  const value=event.payload.model_request_pool
  if(!value||typeof value!=='object'||Array.isArray(value))continue
  const row=value as Record<string,unknown>
  if(row.type!=='model_request_pool'||row.schema!=='capstone-model-request-pool/1'||!text(row.request_id)||!text(row.chain_id)||!['main','analysis'].includes(String(row.kind))||!statuses.has(String(row.status))||!finite(row.queued_at_ms)||!Array.isArray(row.depends_on)||!row.depends_on.every(text))continue
  if(row.kind==='analysis'&&(!text(row.parent_tool_call_id)||!text(row.child_id)))continue
  const next:ProcessModelRequest={id:row.request_id,chainId:row.chain_id,kind:row.kind as 'main'|'analysis',dependsOn:[...row.depends_on],status:row.status as RequestStatus,queuedAtMs:row.queued_at_ms,
   ...(finite(row.model_turn_number)&&row.model_turn_number>0?{modelTurnNumber:row.model_turn_number}:{}),
   ...(typeof row.title==='string'&&row.title.trim()&&row.title.length<=120?{title:row.title}:{}),
   ...(finite(row.started_at_ms)&&row.started_at_ms>=row.queued_at_ms?{startedAtMs:row.started_at_ms}:{}),
   ...(finite(row.finished_at_ms)?{finishedAtMs:row.finished_at_ms}:{}),
   ...(finite(row.first_content_at_ms)?{firstContentAtMs:row.first_content_at_ms}:{}),
   ...(finite(row.cancel_requested_at_ms)?{cancelRequestedAtMs:row.cancel_requested_at_ms}:{}),
   ...(text(row.parent_tool_call_id)?{parentToolCallId:row.parent_tool_call_id}:{}),...(text(row.child_id)?{childId:row.child_id}:{})}
  const prior=requests.get(next.id)
  if(prior&&(prior.chainId!==next.chainId||prior.kind!==next.kind||prior.modelTurnNumber!==next.modelTurnNumber||prior.parentToolCallId!==next.parentToolCallId||prior.childId!==next.childId||prior.queuedAtMs!==next.queuedAtMs))continue
  if(prior&&settled.has(prior.status))continue
  requests.set(next.id,next)
 }
 return [...requests.values()].map(request=>attemptEnded&&!settled.has(request.status)?
  {...request,settlementUnobserved:true}:request)
}
export function requestExecutionMs(request:ProcessModelRequest,now?:number){
 if(request.startedAtMs===undefined||request.settlementUnobserved)return undefined
 const end=request.finishedAtMs??(['running','cancelling'].includes(request.status)?now:undefined)
 return end!==undefined&&Number.isFinite(end)&&end>=request.startedAtMs?end-request.startedAtMs:undefined
}
export function uniqueModelRequests(requests:readonly ProcessModelRequest[]){return [...new Map(requests.map(request=>[request.id,request])).values()]}
export function summarizeModelRequestPool(requests:readonly ProcessModelRequest[],now?:number){
 const unique=uniqueModelRequests(requests),bounds:{at:number;change:number}[]=[]
 for(const request of unique){const elapsed=requestExecutionMs(request,now);if(request.startedAtMs!==undefined&&elapsed!==undefined&&elapsed>0)bounds.push({at:request.startedAtMs,change:1},{at:request.startedAtMs+elapsed,change:-1})}
 bounds.sort((a,b)=>a.at-b.at||a.change-b.change);let concurrent=0,maxConcurrency=0
 for(const bound of bounds){concurrent+=bound.change;maxConcurrency=Math.max(maxConcurrency,concurrent)}
 return {started:unique.filter(request=>request.startedAtMs!==undefined).length,queued:unique.filter(request=>!request.settlementUnobserved&&['queued','waiting_dependencies'].includes(request.status)).length,
  reserved:unique.filter(request=>!request.settlementUnobserved&&['running','cancelling'].includes(request.status)).length,maxConcurrency,
  executionMs:unique.reduce((sum,request)=>sum+(requestExecutionMs(request,now)??0),0)}
}
