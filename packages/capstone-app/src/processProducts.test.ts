import { describe,it,expect } from 'vitest'
import {parseProcessProducts} from './processProducts'
import {readProcessProductResults} from './processProductResults'
import type {AttemptRecords} from './attemptRecords'

const item={product_id:'process_attempt_1',scope:'instruction',thread_id:'thr_1',attempt_id:'attempt_1',work_id:null,
  instruction:'检查模型',status:'failed',event_seq:9,occurred_at:'2026-10-17T10:00:00Z',failure_code:'solver_failed',historical_only:true,model_context:null}
const page={schema:'capstone-process-products/1',thread_id:'thr_1',products:[item],has_more:false,next_before_event_seq:1}
describe('process product catalog',()=>{
  it('preserves failures and explicit historical scope',()=>{
    expect(parseProcessProducts(page,'thr_1').products[0]).toMatchObject({status:'failed',attemptId:'attempt_1',workId:null})
  })
  it('rejects cross-session, duplicate, stale cursor and invented identities',()=>{
    expect(()=>parseProcessProducts(page,'thr_other')).toThrow()
    expect(()=>parseProcessProducts({...page,products:[item,item]},'thr_1')).toThrow()
    expect(()=>parseProcessProducts({...page,has_more:true,next_before_event_seq:10},'thr_1',10)).toThrow()
    expect(()=>parseProcessProducts({...page,products:[{...item,historical_only:false}]},'thr_1')).toThrow()
    expect(()=>parseProcessProducts({...page,products:[{...item,product_id:'invented'}]},'thr_1')).toThrow()
  })
})
describe('historical result recovery',()=>{
  const records:AttemptRecords={threadId:'thr_1',attemptId:'attempt_1',instruction:'检查',modelContext:null,events:[],nextAfter:0,hasMore:false}
  it('keeps failed attempts without results as empty, not fabricated products',async()=>{
    expect(await readProcessProductResults('thr_1','attempt_1',async()=>records)).toEqual([])
  })
  it('rejects cross-session records and stuck pagination',async()=>{
    await expect(readProcessProductResults('thr_1','attempt_1',async()=>({...records,threadId:'other'}))).rejects.toThrow()
    await expect(readProcessProductResults('thr_1','attempt_1',async()=>({...records,hasMore:true}))).rejects.toThrow()
  })
  it('stops recovery when the reader selects another instruction',async()=>{
    const controller=new AbortController();controller.abort()
    await expect(readProcessProductResults('thr_1','attempt_1',async()=>records,controller.signal)).rejects.toThrow()
  })
})
