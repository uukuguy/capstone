import {initializeApplicationCapacity} from './applicationCapacity'
import {afterEach,expect,it} from 'vitest'
import {parseProductRef,parseProductIndex,productRefKey,productSelectionKey,parseContextProductRefs,latestProductVersions,type ProductEntry} from './threadProducts'

export const ref={schema:'capstone-product-ref/1' as const,thread_id:'thr_one',product_id:'file_one',origin:'native_file' as const,scope:'instruction' as const,event_seq:12,revision:null,digest:'a'.repeat(64),work_id:'work_one',attempt_id:'attempt_one',producer_attempt_id:'child_one'}
export const entry={ref,title:'analysis.csv',media_type:'text/csv',byte_size:7,source_status:'completed',created_at:'2026-10-17T00:00:00Z',download_url:null,source:{},dependencies:[],presentation:{kind:'native_file'},capabilities:{read:true,select:true},selection_unavailable_reason:null,historical_only:true}
it('keeps separate paragraphs and rejects contradictory local identities',()=>{
  const local={schema:'capstone-local-product-selection/1',parent_ref:ref,index_ref:'b'.repeat(64),block_id:'opaque_one',content_digest:'c'.repeat(64),purpose:'historical-context'}
  const first={ref,purpose:'historical-context',local_selection:local}
  const second={...first,local_selection:{...local,block_id:'opaque_two'}}
  const parsed=parseContextProductRefs([first,second],ref.thread_id)
  expect(productSelectionKey(parsed[0])).not.toBe(productSelectionKey(parsed[1]))
  expect(()=>parseContextProductRefs([first,first])).toThrow()
  expect(()=>parseContextProductRefs([{...first,excerpt:{max_bytes:10}}])).toThrow()
  expect(()=>parseContextProductRefs([{...first,local_selection:{...local,parent_ref:{...ref,digest:'d'.repeat(64)}}}])).toThrow()
  expect(()=>parseContextProductRefs([{...first,local_selection:{...local,content_digest:'forged'}}])).toThrow()
})
it('preserves exact cross-Work identity and separates task revisions',()=>{
  initializeApplicationCapacity({product_excerpt_bytes:24576})
  expect(parseProductRef(ref,'thr_one')).toEqual(ref)
  expect(()=>parseProductRef({...ref,thread_id:'thr_other'},'thr_one')).toThrow()
  expect(()=>parseProductRef({...ref,extra:'guess'},'thr_one')).toThrow()
  const delivery={...ref,origin:'task_delivery',scope:'task',revision:1}
  expect(productRefKey(parseProductRef(delivery,'thr_one'))).not.toBe(productRefKey(parseProductRef({...delivery,revision:2},'thr_one')))
  expect(parseContextProductRefs([{ref,purpose:'historical-context',excerpt:{max_bytes:24576}}])[0].excerpt).toEqual({max_bytes:24576})
  expect(()=>parseContextProductRefs([{ref,purpose:'historical-context',excerpt:{max_bytes:24577}}])).toThrow()
})
it('admits only bounded same-Thread index entries and rejects contradictory selection',()=>{
  const page={schema:'capstone-product-index/1',thread_id:'thr_one',products:[entry],has_more:false,next_cursor:null}
  expect(parseProductIndex(page,'thr_one').products).toEqual([entry])
  expect(()=>parseProductIndex({...page,products:[{...entry,ref:{...ref,thread_id:'other'}}]},'thr_one')).toThrow()
  expect(()=>parseProductIndex({...page,has_more:true},'thr_one')).toThrow()
  expect(()=>parseProductIndex({...page,products:[{...entry,capabilities:{read:true,select:false}}]},'thr_one')).toThrow()
})

afterEach(()=>initializeApplicationCapacity())

it('shows latest proven host file version and preserves exact historic references',()=>{
 const first={...entry,source:{task_id:'task-one',host_artifact_id:'file-path-'+ref.digest}} as ProductEntry
 const digest='b'.repeat(64)
 const second={...first,ref:{...ref,event_seq:13,digest,product_id:'second'},source:{task_id:'task-one',host_artifact_id:'file-path-'+digest}}
 const other={...first,ref:{...ref,product_id:'other'},source:{task_id:'task-two',host_artifact_id:'file-path-'+ref.digest}}
 const result=latestProductVersions([first,second,other])
 expect(result.latest).toEqual([second,other]);expect(result.history).toEqual([first])
 expect(result.history[0].ref).toBe(first.ref)
 expect(latestProductVersions([{...first,source:{}},second]).latest).toHaveLength(2)
})
