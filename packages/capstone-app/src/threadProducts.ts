import {exceedsCapacity,assertCapacity} from './applicationCapacity'
import {parseResultProjection,type ResultProjection} from './threadProtocol'

export type ProductOrigin='native_file'|'task_delivery'|'domain_result'|'process_record'
export type ProductRef={schema:'capstone-product-ref/1';thread_id:string;product_id:string;origin:ProductOrigin;scope:'instruction'|'task';event_seq:number;revision:number|null;digest:string;work_id:string|null;attempt_id:string|null;producer_attempt_id:string|null}
export type ContextProductRef={ref:ProductRef;purpose:'historical-context';excerpt?:{max_bytes:number}}
export type ProductEntry={ref:ProductRef;title:string;media_type:string|null;byte_size:number|null;source_status:string;created_at:string;download_url:string|null;source:Record<string,unknown>;dependencies:ProductRef[];presentation:Record<string,unknown>&{kind:ProductOrigin};capabilities:{read:true;select:boolean;select_excerpt?:boolean};selection_unavailable_reason:string|null;historical_only:true}
export type ProductIndex={products:ProductEntry[];hasMore:boolean;nextCursor:string|null}
export type ProductResolution={entry:ProductEntry;bytes:Uint8Array|null;projection:ResultProjection|null;record:Record<string,unknown>|null}
export type ProductQuery={cursor?:string;workId?:string|null}
/** Group only proven host file lineage, never titles or basenames. */
export function latestProductVersions(items:ProductEntry[]){
  const newest=new Map<string,ProductEntry>()
  const key=(item:ProductEntry)=>{
    const host=item.source.host_artifact_id,digest=item.ref.digest
    return item.ref.origin==='native_file'&&typeof host==='string'&&host.endsWith('-'+digest)
      ?JSON.stringify([item.ref.thread_id,item.source.task_id,host.slice(0,-digest.length-1)])
      :productRefKey(item.ref)
  }
  for(const item of items){const id=key(item),prior=newest.get(id);if(!prior||item.ref.event_seq>prior.ref.event_seq)newest.set(id,item)}
  const selected=new Set([...newest.values()])
  return {latest:items.filter(item=>selected.has(item)),history:items.filter(item=>!selected.has(item))}
}
const origins=new Set(['native_file','task_delivery','domain_result','process_record'])
const hash=/^[a-f0-9]{64}$/
const identity=(value:unknown):value is string=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$/.test(value)
function object(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('成果信息无效');return value as Record<string,unknown>}
export function parseProductRef(value:unknown,threadId?:string):ProductRef {
  const ref=object(value)
  if(Object.keys(ref).sort().join(',')!=='attempt_id,digest,event_seq,origin,producer_attempt_id,product_id,revision,schema,scope,thread_id,work_id'
    ||ref.schema!=='capstone-product-ref/1'||!identity(ref.thread_id)||threadId!==undefined&&ref.thread_id!==threadId||!identity(ref.product_id)
    ||!origins.has(String(ref.origin))||ref.scope!==(ref.origin==='task_delivery'?'task':'instruction')
    ||!Number.isSafeInteger(ref.event_seq)||(ref.event_seq as number)<1||typeof ref.digest!=='string'||!hash.test(ref.digest)
    ||(ref.origin==='task_delivery'? !Number.isSafeInteger(ref.revision)||(ref.revision as number)<1:ref.revision!==null)
    ||![ref.work_id,ref.attempt_id,ref.producer_attempt_id].every(item=>item===null||identity(item)))throw new Error('成果归属或版本无效')
  return {...ref} as ProductRef
}
export function productRefKey(ref:ProductRef):string {
  return JSON.stringify([ref.thread_id,ref.product_id,ref.origin,ref.scope,ref.event_seq,ref.revision,ref.digest,ref.work_id,ref.attempt_id,ref.producer_attempt_id])
}
export function parseContextProductRefs(value:unknown,threadId?:string):ContextProductRef[] {
  if(!Array.isArray(value)||exceedsCapacity(value.length,'product_reference_count'))throw new Error('成果引用无效')
  const refs=value.map(item=>{const selection=object(item);if(!['purpose,ref','excerpt,purpose,ref'].includes(Object.keys(selection).sort().join(','))||selection.purpose!=='historical-context')throw new Error('成果引用用途无效')
    if(selection.excerpt!==undefined){const excerpt=object(selection.excerpt);if(Object.keys(excerpt).join(',')!=='max_bytes'||!Number.isSafeInteger(excerpt.max_bytes)||(excerpt.max_bytes as number)<1||exceedsCapacity(excerpt.max_bytes as number,'product_excerpt_bytes'))throw new Error('成果摘录范围无效')}
    return {ref:parseProductRef(selection.ref,threadId),purpose:'historical-context' as const,...(selection.excerpt===undefined?{}:{excerpt:{max_bytes:(selection.excerpt as {max_bytes:number}).max_bytes}})}})
  if(new Set(refs.map(item=>productRefKey(item.ref))).size!==refs.length)throw new Error('成果引用重复')
  return refs
}
export function parseProductEntry(value:unknown,threadId:string):ProductEntry {
  const entry=object(value),ref=parseProductRef(entry.ref,threadId),capabilities=object(entry.capabilities),presentation=object(entry.presentation)
  if(typeof entry.title!=='string'||!entry.title.trim()||exceedsCapacity(entry.title.length,'ui_delivery_title_chars')||!(ref.origin==='process_record'&&entry.media_type===null||typeof entry.media_type==='string'&&entry.media_type.length<=256)
    ||!(ref.origin==='process_record'&&entry.byte_size===null||Number.isSafeInteger(entry.byte_size)&&(entry.byte_size as number)>=0&&!exceedsCapacity(entry.byte_size as number,'product_bytes'))
    ||typeof entry.source_status!=='string'||entry.source_status.length>64||typeof entry.created_at!=='string'||!Number.isFinite(Date.parse(entry.created_at))
    ||!(entry.download_url===null||typeof entry.download_url==='string'&&entry.download_url.startsWith(`/api/v1/threads/${encodeURIComponent(threadId)}/`)&&!/[\u0000-\u0020\u007f]/.test(entry.download_url))
    ||!Array.isArray(entry.dependencies)||exceedsCapacity(entry.dependencies.length,'context_references')||presentation.kind!==ref.origin||capabilities.read!==true||typeof capabilities.select!=='boolean'||capabilities.select_excerpt!==undefined&&typeof capabilities.select_excerpt!=='boolean'
    ||(capabilities.select?entry.selection_unavailable_reason!==null:typeof entry.selection_unavailable_reason!=='string'||!entry.selection_unavailable_reason)
    ||entry.historical_only!==true)throw new Error('成果目录条目无效')
  return {...entry,ref,source:object(entry.source),presentation,dependencies:entry.dependencies.map(item=>parseProductRef(item,threadId))} as ProductEntry
}
export function parseProductIndex(value:unknown,threadId:string):ProductIndex {
  const page=object(value)
  if(page.schema!=='capstone-product-index/1'||page.thread_id!==threadId||!Array.isArray(page.products)||exceedsCapacity(page.products.length,'product_page_items')||typeof page.has_more!=='boolean'
    ||!(page.next_cursor===null||typeof page.next_cursor==='string'&&page.next_cursor.length>0&&page.next_cursor.length<=4096)||page.has_more&&page.next_cursor===null)throw new Error('成果目录无效')
  const products=page.products.map(item=>parseProductEntry(item,threadId))
  if(new Set(products.map(item=>productRefKey(item.ref))).size!==products.length)throw new Error('成果目录重复')
  return {products,hasMore:page.has_more,nextCursor:page.next_cursor as string|null}
}
/** File bytes are checked independently; admitted projections remain host-verified contracts. */
export async function parseProductResolution(value:unknown,ref:ProductRef):Promise<ProductResolution> {
  const body=object(value)
  if(body.schema!=='capstone-product-resolution/1')throw new Error('成果读取响应无效')
  const entry=parseProductEntry(body.entry,ref.thread_id)
  if(productRefKey(entry.ref)!==productRefKey(ref))throw new Error('成果版本已变化')
  let bytes:Uint8Array|null=null,projection:ResultProjection|null=null
  if(ref.origin==='domain_result'){
    if(body.content_base64!==null)throw new Error('成果响应类型不符')
    projection=parseResultProjection(body.projection)
    if(projection.threadId!==ref.thread_id||projection.attemptId!==ref.attempt_id||projection.resultId!==entry.source.result_id)throw new Error('分析结果归属不符')
  }else if(ref.origin==='process_record'){
    if(body.content_base64!==null||body.projection!==null)throw new Error('过程记录不包含文件')
  }else{
    if(typeof body.content_base64!=='string'||body.projection!==null)throw new Error('成果文件响应无效')
    const estimatedBytes=Math.floor(body.content_base64.length*3/4)-(body.content_base64.endsWith('==')?2:body.content_base64.endsWith('=')?1:0)
    assertCapacity(estimatedBytes,'product_bytes','product.resolve.bytes')
    const binary=atob(body.content_base64)
    bytes=Uint8Array.from(binary,char=>char.charCodeAt(0))
    const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(bytes).buffer))].map(byte=>byte.toString(16).padStart(2,'0')).join('')
    if(bytes.byteLength!==entry.byte_size||digest!==ref.digest)throw new Error('成果文件校验失败')
  }
  const record=ref.origin==='process_record'?object(body.record):null
  if(record&&(record.thread_id!==ref.thread_id||record.attempt_id!==ref.attempt_id))throw new Error('执行记录归属不符')
  return {entry,bytes,projection,record}
}
