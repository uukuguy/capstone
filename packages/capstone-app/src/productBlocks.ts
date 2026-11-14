import {parseProductRef,productRefKey,type ProductRef} from './threadProducts'
import {applicationCapacity} from './applicationCapacity'

export type BlockJob={job_id:string;state:'queued'|'running'|'ready'|'failed';parent_ref:ProductRef}
export type BlockPage={index_ref:string;blocks:{block_id:string;byte_start:number;byte_end:number;content_digest:string}[];next_offset:number|null}
export type BlockReader=(ref:ProductRef,job?:string,offset?:number,signal?:AbortSignal)=>Promise<{job:BlockJob;page?:BlockPage}>
const hash=/^[a-f0-9]{64}$/
const id=/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/
export function parseBlockJob(value:unknown,ref:ProductRef,jobId?:string):BlockJob {
  const job=value as Record<string,unknown>
  if(!job||job.schema!=='capstone-product-index-job/1'||typeof job.job_id!=='string'||!id.test(job.job_id)
    ||jobId!==undefined&&job.job_id!==jobId||!['queued','running','ready','failed'].includes(String(job.state))
    ||productRefKey(parseProductRef(job.parent_ref,ref.thread_id))!==productRefKey(ref))throw new Error('段落索引状态无效')
  return {job_id:job.job_id,state:job.state as BlockJob['state'],parent_ref:ref}
}
export function parseBlockPage(value:unknown,ref:ProductRef,job:string,offset:number):BlockPage {
  const page=value as Record<string,unknown>
  if(!page||page.schema!=='capstone-product-block-page/1'||page.job_id!==job
    ||productRefKey(parseProductRef(page.parent_ref,ref.thread_id))!==productRefKey(ref)
    ||typeof page.index_ref!=='string'||!hash.test(page.index_ref)||!Array.isArray(page.blocks)
    ||page.blocks.length>applicationCapacity('product_page_items'))throw new Error('段落索引页无效')
  const blocks=page.blocks.map((block:BlockPage['blocks'][number])=>{
    if(!block||typeof block.block_id!=='string'||!id.test(block.block_id)||typeof block.content_digest!=='string'||!hash.test(block.content_digest)
      ||!Number.isSafeInteger(block.byte_start)||!Number.isSafeInteger(block.byte_end)||block.byte_start<0||block.byte_end<=block.byte_start)throw new Error('段落范围无效')
    return {block_id:block.block_id,byte_start:block.byte_start,byte_end:block.byte_end,content_digest:block.content_digest}
  })
  if(new Set(blocks.map(block=>block.block_id)).size!==blocks.length
    ||page.next_offset!==null&&(!blocks.length||page.next_offset!==offset+blocks.length))throw new Error('段落分页无效')
  return {index_ref:page.index_ref,blocks,next_offset:page.next_offset as number|null}
}
