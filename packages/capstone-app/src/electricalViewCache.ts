import {ELECTRICAL_DETAIL_STREAMS,parseElectricalViewOpen,parseElectricalViewPage,type ElectricalStream,type ElectricalViewPage,type ElectricalViewReady} from './electricalModelView'

export type ElectricalDetailStream=typeof ELECTRICAL_DETAIL_STREAMS[number]
export interface ElectricalStreamCheckpoint {
  version:1; identity:string; stream:ElectricalDetailStream; total:number; loaded:number
  cursor:string|null; complete:boolean; pages:number
}
export type ElectricalCheckpoints=Partial<Record<ElectricalStream,ElectricalStreamCheckpoint>>
export interface ElectricalViewStore {
  initialize(manifest:ElectricalViewReady):Promise<ElectricalCheckpoints>
  commitPage(manifest:ElectricalViewReady,stream:ElectricalStream,before:ElectricalStreamCheckpoint,page:ElectricalViewPage,signal?:AbortSignal):Promise<ElectricalStreamCheckpoint>
  getRecord(viewRef:string,stream:ElectricalStream,id:string):Promise<unknown|undefined>
  close?():void
}
export class ElectricalCacheError extends Error {constructor(public readonly code:string){super(code);this.name='ElectricalCacheError'}}
const fail=(code:string):never=>{throw new ElectricalCacheError(code)}
export const ELECTRICAL_CACHE_LIMITS={bytes:1024**3,records:5_000_000,pages:50_000,pageBytes:4*1024**2} as const
const identityFields=['schema','model_ref','model_revision','view_ref','source_snapshot_ref','selection_ref'] as const
const integer=(value:number)=>Number.isSafeInteger(value)&&value>=0
function detail(stream:ElectricalStream):asserts stream is ElectricalDetailStream {
  if(!ELECTRICAL_DETAIL_STREAMS.includes(stream as ElectricalDetailStream))fail('cache_detail_stream_required')
}
export function electricalCacheIdentity(manifest:ElectricalViewReady):string {
  const ready=parseElectricalViewOpen(manifest)
  if(ready.state!=='ready')throw new ElectricalCacheError('cache_view_not_ready')
  const total=ELECTRICAL_DETAIL_STREAMS.reduce((sum,stream)=>sum+ready.streams[stream].total_count,0)
  if(!integer(total)||total>ELECTRICAL_CACHE_LIMITS.records)fail('cache_record_budget_exceeded')
  return JSON.stringify([1,...identityFields.map(field=>ready[field]??null),ready.representation,
    ELECTRICAL_DETAIL_STREAMS.map(stream=>[stream,ready.streams[stream].total_count])])
}
export function initialElectricalCheckpoint(manifest:ElectricalViewReady,stream:ElectricalStream):ElectricalStreamCheckpoint {
  detail(stream);const total=manifest.streams[stream].total_count
  return {version:1,identity:electricalCacheIdentity(manifest),stream,total,loaded:0,cursor:null,complete:total===0,pages:0}
}
export function validateElectricalCheckpoint(manifest:ElectricalViewReady,stream:ElectricalStream,value:ElectricalStreamCheckpoint):void {
  detail(stream)
  if(!value||value.version!==1||value.identity!==electricalCacheIdentity(manifest)||value.stream!==stream
    ||value.total!==manifest.streams[stream].total_count||!integer(value.loaded)||value.loaded>value.total
    ||!integer(value.pages)||value.pages>ELECTRICAL_CACHE_LIMITS.pages||typeof value.complete!=='boolean'
    ||!(value.cursor===null||typeof value.cursor==='string'&&value.cursor.length>0)
    ||value.complete!==(value.loaded===value.total)||value.complete&&value.cursor!==null
    ||!value.complete&&value.loaded>0&&value.cursor===null||value.pages===0&&value.loaded!==0)fail('cache_checkpoint_invalid')
}
/** Pure admission shared with transactional stores; cross-page uniqueness is stored on disk. */
export function validateElectricalCachedPage(manifest:ElectricalViewReady,stream:ElectricalStream,before:ElectricalStreamCheckpoint,value:ElectricalViewPage):ElectricalStreamCheckpoint {
  validateElectricalCheckpoint(manifest,stream,before)
  const page=parseElectricalViewPage(value)
  if(before.complete)fail('cache_stream_already_complete')
  for(const field of identityFields)if(page[field]!==manifest[field])fail('frozen_baseline_mismatch')
  if(page.stream!==stream||page.total_count!==before.total||page.returned_count>500)fail('stream_manifest_mismatch')
  const loaded=before.loaded+page.returned_count
  if(loaded>before.total||page.complete&&loaded!==before.total||!page.complete&&(!page.returned_count||loaded>=before.total))fail('incomplete_stream')
  if(page.next_cursor!==null&&page.next_cursor===before.cursor)fail('cursor_cycle')
  if(before.pages>=ELECTRICAL_CACHE_LIMITS.pages)fail('cache_page_budget_exceeded')
  const bytes=new TextEncoder().encode(JSON.stringify(page)).byteLength
  if(bytes>ELECTRICAL_CACHE_LIMITS.pageBytes)fail('cache_page_bytes_exceeded')
  return {...before,loaded,cursor:page.next_cursor,complete:page.complete,pages:before.pages+1}
}

type Usage={bytes:number;records:number;pages:number}
function request<T>(value:IDBRequest<T>):Promise<T>{return new Promise((resolve,reject)=>{value.onsuccess=()=>resolve(value.result);value.onerror=()=>reject(value.error??new ElectricalCacheError('cache_request_failed'))})}
function cacheError(error:unknown):Error {
  if(error instanceof ElectricalCacheError)return error
  if(error instanceof DOMException&&error.name==='AbortError')return error
  return new ElectricalCacheError(error instanceof DOMException&&error.name==='QuotaExceededError'?'cache_quota_exceeded':'cache_unavailable')
}
/** No memory fallback: quota/unavailable state must remain visible to the caller. */
export function createIndexedDBElectricalViewStore(options:{indexedDB?:IDBFactory;databaseName?:string;maxBytes?:number}={}):ElectricalViewStore {
  let database:Promise<IDBDatabase>|undefined,closed=false
  const maxBytes=options.maxBytes??ELECTRICAL_CACHE_LIMITS.bytes
  const open=()=>database??=(async()=>{
    if(!integer(maxBytes)||maxBytes<1||maxBytes>ELECTRICAL_CACHE_LIMITS.bytes)fail('cache_budget_invalid')
    if(closed)fail('cache_closed')
    const factory=options.indexedDB??globalThis.indexedDB
    if(!factory)fail('cache_unavailable')
    return new Promise<IDBDatabase>((resolve,reject)=>{
      const opening=factory.open(options.databaseName??'capstone-electrical-details',1)
      opening.onupgradeneeded=()=>{for(const name of ['views','checkpoints','records','cursors','usage'])opening.result.createObjectStore(name)}
      opening.onerror=()=>reject(cacheError(opening.error))
      let blocked=false
      opening.onblocked=()=>{blocked=true;reject(new ElectricalCacheError('cache_upgrade_blocked'))}
      opening.onsuccess=()=>{const db=opening.result;if(blocked||closed){db.close();reject(new ElectricalCacheError('cache_closed'));return}db.onversionchange=()=>db.close();resolve(db)}
    })
  })()
  async function transaction<T>(stores:string[],mode:IDBTransactionMode,run:(tx:IDBTransaction)=>Promise<T>,signal?:AbortSignal):Promise<T>{
    signal?.throwIfAborted();if(closed)fail('cache_closed');const db=await open();signal?.throwIfAborted()
    const tx=db.transaction(stores,mode)
    const abort=()=>{try{tx.abort()}catch{/* Already committed. */}}
    signal?.addEventListener('abort',abort,{once:true})
    const finished=new Promise<void>((resolve,reject)=>{tx.oncomplete=()=>resolve();tx.onabort=()=>reject(cacheError(tx.error??new DOMException('Aborted','AbortError')));tx.onerror=()=>{/* Abort delivers the final transaction error. */}})
    try {
      const result=await run(tx);await finished;signal?.throwIfAborted();return result
    } catch(error){abort();await finished.catch(()=>{});throw cacheError(error)}
    finally{signal?.removeEventListener('abort',abort)}
  }
  return {
    async initialize(manifest){
      const identity=electricalCacheIdentity(manifest)
      return transaction(['views','checkpoints'],'readwrite',async tx=>{
        const views=tx.objectStore('views'),saved=await request(views.get(manifest.view_ref)) as string|undefined
        if(saved!==undefined&&saved!==identity)fail('cache_identity_mismatch')
        if(saved===undefined)views.add(identity,manifest.view_ref)
        const checkpoints:ElectricalCheckpoints={}
        for(const stream of ELECTRICAL_DETAIL_STREAMS){
          const key=[manifest.view_ref,stream],store=tx.objectStore('checkpoints')
          let checkpoint=await request(store.get(key)) as ElectricalStreamCheckpoint|undefined
          if(saved!==undefined&&!checkpoint)fail('cache_checkpoint_missing')
          if(checkpoint)validateElectricalCheckpoint(manifest,stream,checkpoint)
          else {checkpoint=initialElectricalCheckpoint(manifest,stream);store.add(checkpoint,key)}
          checkpoints[stream]=checkpoint
        }
        return checkpoints
      })
    },
    async commitPage(manifest,stream,before,page,signal){
      const next=validateElectricalCachedPage(manifest,stream,before,page)
      const pageBytes=new TextEncoder().encode(JSON.stringify(page)).byteLength
      return transaction(['views','checkpoints','records','cursors','usage'],'readwrite',async tx=>{
        const identity=await request(tx.objectStore('views').get(manifest.view_ref))
        if(identity!==before.identity)fail('cache_identity_mismatch')
        const checkpoints=tx.objectStore('checkpoints'),key=[manifest.view_ref,stream]
        const actual=await request(checkpoints.get(key)) as ElectricalStreamCheckpoint|undefined
        if(JSON.stringify(actual)!==JSON.stringify(before))fail('cache_checkpoint_conflict')
        const usageStore=tx.objectStore('usage'),usage=(await request(usageStore.get('total'))??{bytes:0,records:0,pages:0}) as Usage
        if(!integer(usage.bytes)||!integer(usage.records)||!integer(usage.pages))fail('cache_usage_invalid')
        if(usage.bytes+pageBytes>maxBytes)fail('cache_quota_exceeded')
        if(usage.records+page.returned_count>ELECTRICAL_CACHE_LIMITS.records||usage.pages+1>ELECTRICAL_CACHE_LIMITS.pages)fail('cache_budget_exceeded')
        // add() enforces unique IDs and cursor history in the same transaction
        // as the checkpoint. A duplicate rolls back every record in this page.
        const records=tx.objectStore('records'),pending:Promise<unknown>[]=[]
        for(const row of page.records)pending.push(request(records.add(row,[manifest.view_ref,stream,row.id])).catch(error=>{
          if(error instanceof DOMException&&error.name==='ConstraintError')fail('duplicate_record');throw error
        }))
        if(page.next_cursor!==null)pending.push(request(tx.objectStore('cursors').add(true,[manifest.view_ref,stream,page.next_cursor])).catch(error=>{
          if(error instanceof DOMException&&error.name==='ConstraintError')fail('cursor_cycle');throw error
        }))
        pending.push(request(checkpoints.put(next,key)))
        pending.push(request(usageStore.put({bytes:usage.bytes+pageBytes,records:usage.records+page.returned_count,pages:usage.pages+1},'total')))
        await Promise.all(pending);return next
      },signal)
    },
    async getRecord(viewRef,stream,id){
      detail(stream)
      return transaction(['records'],'readonly',async tx=>request(tx.objectStore('records').get([viewRef,stream,id])))
    },
    close(){closed=true;void database?.then(db=>db.close(),()=>{})},
  }
}
