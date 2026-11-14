import {expect,it} from 'vitest'
import {parseBlockJob,parseBlockPage} from './productBlocks'
import {parseProductRef} from './threadProducts'

const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'file_one',origin:'native_file',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:null,producer_attempt_id:null})
it('binds pages and status to the exact parent and job',()=>{
  const job={schema:'capstone-product-index-job/1',job_id:'job_one',state:'ready',parent_ref:ref}
  expect(parseBlockJob(job,ref).state).toBe('ready')
  expect(()=>parseBlockJob(job,ref,'other')).toThrow()
  const page={schema:'capstone-product-block-page/1',job_id:'job_one',parent_ref:ref,index_ref:'b'.repeat(64),blocks:[{block_id:'opaque',byte_start:0,byte_end:4,content_digest:'c'.repeat(64)}],next_offset:1}
  expect(parseBlockPage(page,ref,'job_one',0).next_offset).toBe(1)
  expect(()=>parseBlockPage({...page,next_offset:0},ref,'job_one',0)).toThrow()
  expect(()=>parseBlockPage({...page,parent_ref:{...ref,digest:'d'.repeat(64)}},ref,'job_one',0)).toThrow()
})
