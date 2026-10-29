import type {EventEnvelope} from './threadProtocol'
export type LlmPoolStatus='queued'|'waiting_dependencies'|'running'|'cancelling'|'completed'|'failed'|'cancelled'|'blocked'
export type ProcessLlmPoolCall={id:string;parentToolCallId:string;title:string;status:LlmPoolStatus;queuedAtMs:number;startedAtMs?:number;finishedAtMs?:number;responseCount?:number;responseMs?:number}
const statuses=new Set(['queued','waiting_dependencies','running','cancelling','completed','failed','cancelled','blocked'])
const nonnegative=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value)&&value>=0
/** Host-admitted public calls only; never infer parents from nearby timestamps. */
export function projectLlmPoolCalls(events:readonly EventEnvelope[],attemptId:string):ProcessLlmPoolCall[]{
 const submits=new Set<string>(),calls=new Map<string,ProcessLlmPoolCall>(),responses=new Map<string,Map<number,number>>()
 for(const event of events){
  if(event.attemptId!==attemptId||event.visibility!=='public'||event.eventType!=='runtime_event')continue
  const payload=event.payload
  if(payload.native_type==='tool_execution_start'&&payload.tool_name==='agent_llm_submit'&&typeof payload.tool_call_id==='string')submits.add(payload.tool_call_id)
  if(payload.native_type!=='llm_pool_call')continue
  const value=payload.llm_pool_call
  if(!value||typeof value!=='object'||Array.isArray(value))continue
  const row=value as Record<string,unknown>
  if(row.type!=='llm_pool_call'||row.schema!=='capstone-llm-call-pool/1'||typeof row.parent_tool_call_id!=='string'||!submits.has(row.parent_tool_call_id)||typeof row.child_id!=='string'||!row.child_id||typeof row.title!=='string'||!row.title.trim()||row.title.length>120||typeof row.status!=='string'||!statuses.has(row.status)||!nonnegative(row.queued_at_ms))continue
  const key=JSON.stringify([row.parent_tool_call_id,row.child_id]),prior=calls.get(key)
  if(prior&&(prior.title!==row.title||prior.queuedAtMs!==row.queued_at_ms))continue
  const timing=responses.get(key)??new Map<number,number>();responses.set(key,timing)
  if(Number.isSafeInteger(row.response_number)&&Number(row.response_number)>0&&nonnegative(row.response_ms)&&!timing.has(Number(row.response_number)))timing.set(Number(row.response_number),row.response_ms)
  const terminal=['completed','failed','cancelled','blocked'].includes(row.status)
  const reported=Number.isSafeInteger(row.model_responses)&&Number(row.model_responses)>=0?Number(row.model_responses):undefined
  const observed=timing.size?Math.max(...timing.keys()):0
  const responseCount=reported===undefined?(observed||(!terminal?0:undefined)):Math.max(reported,observed)
  calls.set(key,{id:row.child_id,parentToolCallId:row.parent_tool_call_id,title:row.title,status:row.status as LlmPoolStatus,queuedAtMs:row.queued_at_ms,
   ...(nonnegative(row.started_at_ms)?{startedAtMs:row.started_at_ms}:{}),...(nonnegative(row.finished_at_ms)?{finishedAtMs:row.finished_at_ms}:{}),
   responseCount,...(timing.size&&timing.size===responseCount?{responseMs:[...timing.values()].reduce((sum,ms)=>sum+ms,0)}:{})})
 }
 return [...calls.values()]
}
export function summarizeLlmPoolCalls(calls:readonly ProcessLlmPoolCall[]){
 const unique=[...new Map(calls.map(call=>[JSON.stringify([call.parentToolCallId,call.id]),call])).values()]
 return {responses:unique.every(call=>call.responseCount!==undefined)?unique.reduce((sum,call)=>sum+call.responseCount!,0):undefined,
  responseMs:unique.every(call=>call.responseMs!==undefined||call.responseCount===0)?unique.reduce((sum,call)=>sum+(call.responseMs??0),0):undefined}
}
