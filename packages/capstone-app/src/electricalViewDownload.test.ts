import {expect,it,vi} from 'vitest'
import {createElectricalViewDownload,type ElectricalDownloadProgress} from './electricalViewDownload'
import {electricalOverviewManifest,electricalOverviewRecords,electricalPage} from './electricalModelFixtures'
import {ELECTRICAL_DETAIL_STREAMS,type ElectricalReadRequest,type ElectricalViewReady,type ElectricalViewPage,type ElectricalStream} from './electricalModelView'
import {electricalCacheIdentity,initialElectricalCheckpoint,validateElectricalCachedPage,type ElectricalViewStore,type ElectricalStreamCheckpoint} from './electricalViewCache'

/** Transactional fake: nothing changes until the whole page passes admission. */
class MemoryStore implements ElectricalViewStore {
  identity=''; checkpoints={} as Record<ElectricalStream,ElectricalStreamCheckpoint>
  records=new Map<string,unknown>();cursors=new Set<string>();fail=false
  async initialize(manifest:ElectricalViewReady){
    const identity=electricalCacheIdentity(manifest)
    if(this.identity&&identity!==this.identity)throw Error('cache_identity_mismatch')
    this.identity=identity
    for(const stream of ELECTRICAL_DETAIL_STREAMS)this.checkpoints[stream]??=initialElectricalCheckpoint(manifest,stream)
    return structuredClone(this.checkpoints)
  }
  async commitPage(manifest:ElectricalViewReady,stream:ElectricalStream,before:ElectricalStreamCheckpoint,page:ElectricalViewPage,signal?:AbortSignal){
    if(this.fail)throw Error('cache_quota_exceeded')
    signal?.throwIfAborted()
    const next=validateElectricalCachedPage(manifest,stream,before,page)
    if(JSON.stringify(before)!==JSON.stringify(this.checkpoints[stream]))throw Error('cache_checkpoint_conflict')
    if(page.records.some(row=>this.records.has(`${stream}:${row.id}`)))throw Error('duplicate_record')
    if(page.next_cursor&&this.cursors.has(`${stream}:${page.next_cursor}`))throw Error('cursor_cycle')
    for(const row of page.records)this.records.set(`${stream}:${row.id}`,structuredClone(row))
    if(page.next_cursor)this.cursors.add(`${stream}:${page.next_cursor}`)
    this.checkpoints[stream]=next
    return structuredClone(next)
  }
  async getRecord(_view:string,stream:ElectricalStream,id:string){return this.records.get(`${stream}:${id}`)}
}
const settle=()=>new Promise(resolve=>setTimeout(resolve,0))
async function until(check:()=>boolean){for(let i=0;i<100&&!check();i++)await settle();expect(check()).toBe(true)}
function fixture(){const records=electricalOverviewRecords();return {records,manifest:electricalOverviewManifest(records)}}

it('returns immediately, bounds concurrency to two, and never downloads summaries',async()=>{
  const {records,manifest}=fixture(),store=new MemoryStore(),updates:ElectricalDownloadProgress[]=[]
  let active=0,max=0;const releases:(()=>void)[]=[]
  const read=vi.fn(async(request:ElectricalReadRequest)=>{
    active++;max=Math.max(max,active);await new Promise<void>(resolve=>releases.push(resolve));active--
    expect(request.limit).toBe(500);return electricalPage(manifest,records,request)
  })
  const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),store)
  expect(download.start()).toBeUndefined()
  await until(()=>releases.length===2);expect(updates.at(-1)?.state).toBe('running')
  while(updates.at(-1)?.state==='running'){releases.splice(0).forEach(release=>release());await settle()}
  expect(max).toBe(2);expect(updates.at(-1)?.state).toBe('complete')
  expect(read.mock.calls.every(([request])=>ELECTRICAL_DETAIL_STREAMS.includes(request.stream as typeof ELECTRICAL_DETAIL_STREAMS[number]))).toBe(true)
  expect(updates.at(-1)?.loaded).toBe(ELECTRICAL_DETAIL_STREAMS.reduce((sum,stream)=>sum+records[stream].length,0))
})

it('pauses in-flight work, restores exact committed cursor, and ignores late old-generation callbacks',async()=>{
  const {records,manifest}=fixture();records.devices=Array.from({length:501},(_,i)=>({id:`d${i}`,kind:'breaker'}));manifest.streams.devices.total_count=501
  const store=new MemoryStore(),updates:ElectricalDownloadProgress[]=[];let late:(()=>void)|undefined,signal:AbortSignal|undefined
  const read=vi.fn(async(request:ElectricalReadRequest,abort?:AbortSignal)=>{
    if(request.stream==='devices'&&request.cursor&&!late){signal=abort;await new Promise<void>(resolve=>{late=resolve})}
    return electricalPage(manifest,records,request)
  })
  const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),store)
  download.start();await until(()=>!!late);download.pause();expect(signal?.aborted).toBe(true)
  const count=updates.length;late!();await settle();expect(updates).toHaveLength(count)
  expect(store.checkpoints.devices.loaded).toBe(500)
  download.start();await until(()=>updates.at(-1)?.state==='complete')
  const cursors=read.mock.calls.filter(([request])=>request.stream==='devices').map(([request])=>request.cursor)
  expect(cursors).toEqual([undefined,'cursor:devices:500','cursor:devices:500'])
  expect(await store.getRecord(manifest.view_ref,'devices','d500')).toMatchObject({id:'d500'})
})

it.each(['duplicate','cursor','version','total','stream','empty','cache'])('stops on %s without automatic retry or false completion',async kind=>{
  const {records,manifest}=fixture();records.devices=Array.from({length:1001},(_,i)=>({id:`d${i}`,kind:'breaker'}));manifest.streams.devices.total_count=1001
  const store=new MemoryStore(),updates:ElectricalDownloadProgress[]=[]
  const read=vi.fn(async(request:ElectricalReadRequest)=>{
    const page=electricalPage(manifest,records,request)
    if(request.stream==='devices'){
      if(kind==='duplicate'&&request.cursor)page.records[0]={id:'d0',kind:'breaker'} as never
      if(kind==='cursor'&&request.cursor)page.next_cursor=request.cursor
      if(kind==='version')page.model_revision='changed'
      if(kind==='total')page.total_count++
      if(kind==='stream')page.stream='issues'
      if(kind==='empty'){page.records=[];page.returned_count=0;page.complete=false;page.next_cursor='empty'}
      if(kind==='cache')store.fail=true
    }
    return page
  })
  const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),store)
  download.start();await until(()=>updates.at(-1)?.state==='error')
  const count=read.mock.calls.length;await settle();expect(read).toHaveBeenCalledTimes(count)
  expect(updates.at(-1)?.loaded).toBeLessThan(updates.at(-1)!.total)
  expect(updates.at(-1)?.error).toBeTruthy();download.dispose()
})

it('resumes after an explicit start on cache failure and rejects a reused view with changed manifest totals',async()=>{
  const {records,manifest}=fixture(),store=new MemoryStore(),updates:ElectricalDownloadProgress[]=[]
  store.fail=true
  const read=vi.fn(async(request:ElectricalReadRequest)=>electricalPage(manifest,records,request))
  const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),store)
  download.start();await until(()=>updates.at(-1)?.state==='error');store.fail=false
  download.start();await until(()=>updates.at(-1)?.state==='complete')
  const changed=structuredClone(manifest);changed.streams.devices.total_count++
  const next=createElectricalViewDownload(changed,read,value=>updates.push(value),store)
  const calls=read.mock.calls.length;next.start();await until(()=>updates.at(-1)?.state==='error')
  expect(read).toHaveBeenCalledTimes(calls)
})

it('dispose aborts and suppresses all late callbacks without starting additional pages',async()=>{
  const {records,manifest}=fixture(),updates:ElectricalDownloadProgress[]=[];let release:()=>void=()=>{}
  const read=vi.fn(async(request:ElectricalReadRequest)=>{await new Promise<void>(resolve=>{release=resolve});return electricalPage(manifest,records,request)})
  const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),new MemoryStore())
  download.start();await until(()=>read.mock.calls.length===2);download.dispose();const count=updates.length
  release();await settle();download.start();expect(updates).toHaveLength(count);expect(read).toHaveBeenCalledTimes(2)
})

it('completes an empty detail manifest without reading summary records',async()=>{
  const {manifest}=fixture();for(const stream of ELECTRICAL_DETAIL_STREAMS)manifest.streams[stream].total_count=0
  const read=vi.fn(async()=>({})),updates:ElectricalDownloadProgress[]=[]
  createElectricalViewDownload(manifest,read,value=>updates.push(value),new MemoryStore()).start()
  await until(()=>updates.at(-1)?.state==='complete');expect(read).not.toHaveBeenCalled()
  expect(updates.at(-1)).toMatchObject({loaded:0,total:0})
})

it('bounds a hanging page by a deadline without automatic retry',async()=>{
  vi.useFakeTimers()
  try {
    const {manifest}=fixture(),updates:ElectricalDownloadProgress[]=[],signals:AbortSignal[]=[]
    const read=vi.fn((_request:ElectricalReadRequest,signal?:AbortSignal)=>{signals.push(signal!);return new Promise<unknown>(()=>{})})
    const download=createElectricalViewDownload(manifest,read,value=>updates.push(value),new MemoryStore())
    download.start();await vi.advanceTimersByTimeAsync(0);expect(read).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(updates.at(-1)).toMatchObject({state:'error',error:'page_timeout'})
    expect(signals.every(signal=>signal.aborted)).toBe(true)
    await vi.advanceTimersByTimeAsync(60_000);expect(read).toHaveBeenCalledTimes(2)
    download.dispose()
  } finally{vi.useRealTimers()}
})
