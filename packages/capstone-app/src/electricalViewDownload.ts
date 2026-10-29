import {ELECTRICAL_DETAIL_STREAMS,parseElectricalViewOpen,parseElectricalViewPage,type ElectricalReadRequest,type ElectricalStream,type ElectricalViewReady} from './electricalModelView'
import {createIndexedDBElectricalViewStore,validateElectricalCachedPage,validateElectricalCheckpoint,type ElectricalCheckpoints,type ElectricalViewStore} from './electricalViewCache'

export interface ElectricalDownloadProgress {
  state:'running'|'paused'|'complete'|'error';loaded:number;total:number
  streams:Partial<Record<ElectricalStream,{loaded:number;total:number;complete:boolean}>>;error?:string
}
export interface ElectricalViewDownload {start():void;pause():void;dispose():void}
export type ElectricalViewRead=(request:ElectricalReadRequest,signal?:AbortSignal)=>Promise<unknown>

async function readPage(read:ElectricalViewRead,request:ElectricalReadRequest,parent:AbortSignal):Promise<unknown>{
  const controller=new AbortController()
  let timer:ReturnType<typeof setTimeout>|undefined,abort=()=>{}
  const stopped=new Promise<never>((_resolve,reject)=>{
    abort=()=>{controller.abort();reject(new DOMException('Aborted','AbortError'))}
    parent.addEventListener('abort',abort,{once:true})
    timer=setTimeout(()=>{controller.abort();reject(Error('page_timeout'))},30_000)
  })
  try {parent.throwIfAborted();return await Promise.race([read(request,controller.signal),stopped])}
  finally {clearTimeout(timer);parent.removeEventListener('abort',abort)}
}

/** Independent background transfer. It owns no agent/task or render state. */
export function createElectricalViewDownload(input:ElectricalViewReady,read:ElectricalViewRead,onProgress:(progress:ElectricalDownloadProgress)=>void,optionalStore?:ElectricalViewStore):ElectricalViewDownload {
  // Own the frozen inputs: UI updates must never change an active download.
  const manifest=structuredClone(input)
  const store=optionalStore??createIndexedDBElectricalViewStore()
  let checkpoints:ElectricalCheckpoints={},generation=0,disposed=false,running=false,controller:AbortController|undefined
  const publish=(state:ElectricalDownloadProgress['state'],error?:string)=>{
    if(disposed)return
    const streams:ElectricalDownloadProgress['streams']={};let loaded=0,total=0
    for(const stream of ELECTRICAL_DETAIL_STREAMS){
      const count=manifest.streams[stream].total_count,checkpoint=checkpoints[stream]
      streams[stream]={loaded:checkpoint?.loaded??0,total:count,complete:checkpoint?.complete??count===0}
      loaded+=streams[stream]!.loaded;total+=count
    }
    onProgress({state,loaded,total,streams,...(error?{error}:{})})
  }
  const stop=()=>{generation++;running=false;controller?.abort()}
  async function run(current:number,signal:AbortSignal){
    const active=()=>!disposed&&generation===current&&!signal.aborted
    try {
      const ready=parseElectricalViewOpen(manifest)
      if(ready.state!=='ready')throw Error('view_not_ready')
      const saved=await store.initialize(manifest)
      if(!active())return
      for(const stream of ELECTRICAL_DETAIL_STREAMS)validateElectricalCheckpoint(manifest,stream,saved[stream]!)
      checkpoints=saved;publish('running')
      const queue=ELECTRICAL_DETAIL_STREAMS.filter(stream=>!checkpoints[stream]!.complete)
      async function worker(){
        let stream:typeof ELECTRICAL_DETAIL_STREAMS[number]|undefined
        while(active()&&(stream=queue.shift())!==undefined){
          while(active()&&!checkpoints[stream]!.complete){
            const before=checkpoints[stream]!
            const value=await readPage(read,{view_ref:manifest.view_ref,stream,limit:500,...(before.cursor?{cursor:before.cursor}:{})},signal)
            if(!active())return
            const page=parseElectricalViewPage(value)
            validateElectricalCachedPage(manifest,stream,before,page)
            const next=await store.commitPage(manifest,stream,before,page,signal)
            if(!active())return
            validateElectricalCheckpoint(manifest,stream,next)
            checkpoints[stream]=next;publish('running')
          }
        }
      }
      await Promise.all([worker(),worker()])
      if(active()){running=false;publish('complete')}
    } catch(error){
      if(!active())return
      stop();publish('error',error instanceof Error?error.message:'download_failed')
    }
  }
  return {
    start(){
      if(disposed||running)return
      running=true;const current=++generation;controller=new AbortController()
      publish('running');void run(current,controller.signal)
    },
    pause(){if(disposed)return;stop();publish('paused')},
    dispose(){stop();disposed=true;if(!optionalStore)store.close?.()},
  }
}
