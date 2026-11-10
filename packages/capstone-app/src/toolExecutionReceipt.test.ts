import { describe, expect, it } from 'vitest'
import { parseToolExecutionReceipt, parseToolDispatchReceipt, dispatchBatchSummary, receiptBatchSummary, receiptDuration } from './toolExecutionReceipt'
import { receipt } from './toolExecutionReceipt.fixture'
it('measures native submission through release without using overlap to classify the batch',()=>{
  const native=(id:string,offset:number)=>{
    const base=receipt(id,offset)
    return {...base,schema:'capstone-tool-dispatch/1',scope_id:base.task_id,events:base.events.map(event=>({...event,phase:event.phase==='execution_started'?'invocation_started':event.phase==='execution_ended'?'invocation_settled':event.phase,provenance:'native_dispatch'}))}
  }
  const a=native('a',0),b=native('b',4000)
  const parsed=[parseToolDispatchReceipt(a,'a'),parseToolDispatchReceipt(b,'b')]
  expect(parsed[0]).toEqual(a)
  expect(dispatchBatchSummary(parsed)).toEqual({capacity:8,elapsedMs:b.events.at(-1)!.elapsed_ms-a.events[0].elapsed_ms})
  expect(parseToolDispatchReceipt({...a,scope_id:'foreign'},'a')).toBeUndefined()
  expect(parseToolDispatchReceipt(a,'foreign')).toBeUndefined()
  expect(parseToolExecutionReceipt(a,'a')).toBeUndefined()
  expect(dispatchBatchSummary([parsed[0],undefined])).toEqual({})
})
describe('owner execution receipts',()=>{
  it('admits production owner and scoped call identities while rejecting actual control bytes',()=>{
    const call='graph-child:action-17:call_01u7f'
    const production={...receipt(call),owner_id:'execution-owner-001f007faabbccdd',scope_id:'execution-owner-001f007faabbccdd',task_id:'research-task-0017',policy_version:'rolling/1'}
    expect(parseToolExecutionReceipt(production,call)).toEqual(production)
    for(const key of ['owner_id','scope_id','task_id','policy_version'] as const){
      for(const code of [0,1,15,31,127]){
        expect(parseToolExecutionReceipt({...production,[key]:`prefix${String.fromCharCode(code)}suffix`},call)).toBeUndefined()
      }
    }
    const invalidCall=`call${String.fromCharCode(31)}17`
    expect(parseToolExecutionReceipt({...production,call_id:invalidCall},invalidCall)).toBeUndefined()
  })
  it('accepts queued cancellation without claiming actual execution',()=>{
    const base=receipt(), cancel={phase:'cancellation_requested',at:base.events[1].at,elapsed_ms:100,provenance:'owner_scheduler' as const}
    const queued={...base,events:[...base.events.slice(0,2),cancel]}
    expect(parseToolExecutionReceipt(queued,'c')).toEqual(queued)
    expect(receiptDuration(parseToolExecutionReceipt(queued,'c'),'execution_started','execution_ended')).toBeUndefined()
    expect(receiptBatchSummary([parseToolExecutionReceipt(queued,'c')])).toEqual({capacity:8})
    expect(parseToolExecutionReceipt({...queued,events:[...queued.events,cancel]},'c')).toBeUndefined()
    expect(parseToolExecutionReceipt({...queued,events:[...queued.events,base.events[4]]},'c')).toBeUndefined()
    const released={...queued,events:[...queued.events,base.events[5]]}
    expect(parseToolExecutionReceipt(released,'c')).toEqual(released)
    expect(receiptDuration(parseToolExecutionReceipt(released,'c'),'execution_started','execution_ended')).toBeUndefined()
  })
  it('rejects lease release as a substitute for a missing execution end',()=>{
    const base=receipt()
    expect(parseToolExecutionReceipt({...base,events:[...base.events.slice(0,4),base.events[5]]},'c')).toBeUndefined()
  })
  it('validates identity and finite ordered owner measurements',()=>{
    expect(parseToolExecutionReceipt(receipt(),'c')).toBeDefined()
    expect(parseToolExecutionReceipt(receipt(),'other')).toBeUndefined()
    for(const elapsed_ms of [NaN,Infinity,-1]) expect(parseToolExecutionReceipt({...receipt(),events:[{...receipt().events[0],elapsed_ms}]},'c')).toBeUndefined()
    expect(parseToolExecutionReceipt({...receipt(),events:[receipt().events[3],receipt().events[1]]},'c')).toBeUndefined()
  })
  it('keeps queue time separate and counts sixteen calls with a measured peak of eight',()=>{
    const receipts=Array.from({length:16},(_,index)=>receipt(String(index),index<8?0:1000))
    expect(receiptDuration(receipts[0],'queued','acquired')).toBe(1000)
    expect(receiptDuration(receipts[0],'execution_started','execution_ended')).toBe(1000)
    expect(receiptBatchSummary(receipts)).toEqual({capacity:8,peak:8,elapsedMs:3000})
  })
  it('never invents concurrency for missing receipts or incompatible owner clocks',()=>{
    expect(receiptBatchSummary([receipt(),undefined])).toEqual({})
    expect(receiptBatchSummary([receipt(),{...receipt('b'),scope_id:'another'}])).toEqual({})
    expect(receiptBatchSummary([{...receipt(),events:receipt().events.slice(0,4)}])).toEqual({capacity:8})
  })
})
