import type {EventEnvelope} from './threadProtocol'
import {projectProcessCompactions} from './processCompactions'
import {projectProcessModelRequests} from './processModelRequests'

export const contextCategories = {
  system:'系统提示', tools:'工具定义', messages:'会话消息', tool_results:'工具返回',
} as const
export type Category = keyof typeof contextCategories
type ContextItem={kind:string;index:number;tokens:number;name?:string}
type ContextItems={total:number;items:ContextItem[]}
type Usage = Partial<Record<'input'|'output'|'cacheRead'|'cacheWrite', number>>
export type ContextObservation = {
  id:string
  instructionId:string
  attemptId:string
  sequence:number
  kind:'main'|'analysis'|'summary'|'compaction'
  state:string
  inputTokens?:number
  windowTokens?:number
  basis?:'provider'|'estimate'
  categories?:Partial<Record<Category,number>>
  items?:Partial<Record<Category,ContextItems>>
  usage?:Usage
  reason?:string
  firstKeptEntryId?:string
}

const object = (value:unknown):Record<string,unknown> =>
  value && typeof value==='object' && !Array.isArray(value) ? value as Record<string,unknown> : {}
const count = (value:unknown):value is number =>
  typeof value==='number' && Number.isSafeInteger(value) && value>=0 && value<=100_000_000

function numericFields<Key extends string>(value:unknown, keys:readonly Key[]):Partial<Record<Key,number>> {
  const fields=object(value)
  const entries=keys.flatMap(key=>count(fields[key])?[[key, fields[key]] as const]:[])
  return Object.fromEntries(entries) as Partial<Record<Key,number>>
}

const itemKinds:Record<Category,readonly string[]> = {
  system:['system'],tools:['tool'],messages:['user','assistant','message'],tool_results:['toolResult'],
}
function contextItems(value:unknown):ContextObservation['items'] {
  const result:Partial<Record<Category,ContextItems>>={}
  for(const key of Object.keys(contextCategories) as Category[]){
    const raw=object(object(value)[key])
    if(!count(raw.total_items)||!Array.isArray(raw.items)||raw.items.length>Math.min(raw.total_items,12))continue
    const total=raw.total_items
    const seen=new Set<number>()
    const items=raw.items.flatMap((candidate):ContextItem[]=>{
      const item=object(candidate)
      if(typeof item.kind!=='string'||!itemKinds[key].includes(item.kind)||!count(item.index)||!item.index||item.index>total
        ||!count(item.tokens)||seen.has(item.index))return []
      seen.add(item.index)
      const name=(key==='tools'||key==='tool_results')&&typeof item.name==='string'&&/^[A-Za-z0-9_.:-]{1,100}$/.test(item.name)?item.name:undefined
      return [{kind:item.kind,index:item.index,tokens:item.tokens,name}]
    })
    result[key]={total,items}
  }
  return result
}

function inputUsage(usage:Usage) {
  const {input,cacheRead,cacheWrite}=usage
  return input!==undefined&&cacheRead!==undefined&&cacheWrite!==undefined ? input+cacheRead+cacheWrite : undefined
}

export function projectInstructionContexts(events:readonly EventEnvelope[]):ContextObservation[] {
  const attempts=new Map<string,EventEnvelope[]>()
  for(const event of events){
    if(!event.attemptId||event.visibility!=='public')continue
    const relevant=attempts.get(event.attemptId)
    if(relevant)relevant.push(event)
    else attempts.set(event.attemptId,[event])
  }
  const rows:ContextObservation[]=[]
  for(const [attemptId,stream] of attempts){
    stream.sort((a,b)=>a.eventSeq-b.eventSeq)
    // Retries share the admitted turn. A source attempt on a follow-up
    // does not make the new turn part of the earlier instruction.
    const instructionId=stream.find(event=>event.turnId)?.turnId||attemptId
    const byEvent=new Map(stream.map(event=>[event.eventId,event]))
    const observed=new Map<string,ContextObservation>()
    for(const event of stream){
      if(event.eventType!=='runtime_event')continue
      const raw=object(event.payload.model_context_usage)
      if(typeof raw.request_id!=='string'||!/^ctx-[1-9][0-9]{0,8}$/.test(raw.request_id)
        ||(raw.kind!=='main'&&raw.kind!=='analysis'&&raw.kind!=='summary')||typeof raw.state!=='string')continue
      const prior=observed.get(raw.request_id)
      if(prior&&(prior.kind!==raw.kind||prior.state!=='started'||!['completed','failed'].includes(raw.state)))continue
      if(!prior&&raw.state!=='started')continue
      const usage=numericFields(raw.usage,['input','output','cacheRead','cacheWrite'] as const)
      const categories=numericFields(raw.estimated_input,Object.keys(contextCategories) as Category[])
      const estimate=Object.keys(categories).length ? Object.values(categories).reduce((total,value)=>total+value,0) : undefined
      const measured=raw.state==='completed'?inputUsage(usage):undefined
      observed.set(raw.request_id,{
        id:attemptId+':'+raw.request_id,instructionId,attemptId,sequence:prior?.sequence??event.eventSeq,
        kind:raw.kind,state:raw.state,windowTokens:count(raw.window_tokens)&&raw.window_tokens>0?raw.window_tokens:prior?.windowTokens,
        categories,items:contextItems(raw.input_items),usage,inputTokens:measured??estimate,basis:measured!==undefined?'provider':estimate!==undefined?'estimate':undefined,
      })
    }
    rows.push(...observed.values())
    if(!observed.size){
      for(const call of projectProcessModelRequests(stream,attemptId)){
        const event=byEvent.get(call.id)
        if(!event||call.requestPoolOnly)continue
        const usage=numericFields(call.usage,['input','output','cacheRead','cacheWrite'] as const)
        const inputTokens=inputUsage(usage)
        rows.push({id:call.id,instructionId,attemptId,sequence:event.eventSeq,kind:'main',
          state:call.stopReason==='error'||call.stopReason==='aborted'?'failed':call.settled?'completed':'started',
          usage,inputTokens,basis:inputTokens===undefined?undefined:'provider'})
      }
    }
    for(const phase of projectProcessCompactions(stream,attemptId)){
      const event=byEvent.get(phase.id)
      if(event)rows.push({id:phase.id,instructionId,attemptId,sequence:event.eventSeq,kind:'compaction',
        state:phase.state,reason:phase.reason,firstKeptEntryId:phase.firstKeptEntryId,inputTokens:phase.tokensBefore,basis:phase.tokensBefore===undefined?undefined:'estimate'})
    }
  }
  return rows.sort((a,b)=>a.sequence-b.sequence)
}

const compactTokens=new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1})

export function contextTokenLabel(value:number) {
  return value<1000?String(value):compactTokens.format(value)
}

export function contextPercent(row:ContextObservation) {
  return row.inputTokens===undefined||row.windowTokens===undefined ? undefined : Math.round(row.inputTokens/row.windowTokens*100)
}
