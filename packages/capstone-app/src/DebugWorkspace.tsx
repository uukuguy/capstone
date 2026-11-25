import {useState} from 'react'
import AttemptRecordPanel, {type AttemptRecordReader} from './AttemptRecordPanel'
import {firstDebugObservation} from './debugObservation'

export default function DebugWorkspace({threadId,attempts,through,read,allowExport,readTimeline,savedFinding,sourceVersion}:{
  threadId:string; attempts:string[]; through:number; read:AttemptRecordReader; allowExport:boolean; savedFinding:string; sourceVersion:string
  readTimeline:(attempt:string,after:number,through?:number)=>Promise<{events:{seq:number;type:string}[];hasMore:boolean;nextAfter:number;through:number}>
}){
  const [selection,setSelection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [observation,setObservation]=useState<{attempt:string;text:string}|null>(null)
  const attempt=attempts.includes(selection)?selection:attempts[0]
  async function locate(){
    if(!attempt||busy)return
    setBusy(true)
    setError('')
    try{
      const found=await firstDebugObservation(attempt,read,through)
      setObservation({attempt,text:found?`首条公开异常记录 #${found.seq} · ${found.label}`:
        `截至事件 #${through}，公开记录中未发现工具失败、核验失败或任务失败、中断事件。`})
    }catch(cause){setError(cause instanceof Error?cause.message:'执行记录读取失败。')}
    finally{setBusy(false)}
  }
  async function download(){
    if(!attempt||busy)return
    setBusy(true)
    setError('')
    try{
      const parts:BlobPart[]=[JSON.stringify({schema:'capstone-debug-timeline/1',thread_id:threadId,attempt_id:attempt})+'\n']
      let after=0
      let through:number|undefined
      for(;;){
        const page=await readTimeline(attempt,after,through)
        through=page.through
        for(const event of page.events){
          parts.push(JSON.stringify(event)+'\n')
        }
        if(!page.hasMore)break
        after=page.nextAfter
      }
      const url=URL.createObjectURL(new Blob(parts,{type:'application/x-ndjson'}))
      const link=document.createElement('a')
      link.href=url
      link.download='debug-'+attempt+'.ndjson'
      link.click()
      setTimeout(()=>URL.revokeObjectURL(url),1000)
    }catch(cause){setError(cause instanceof Error?cause.message:'调试记录下载失败。')}
    finally{setBusy(false)}
  }
  if(!attempt)return <section aria-label="Debug"><p>{sourceVersion}</p><p>{savedFinding||'当前会话还没有执行记录。'}</p></section>
  return <section aria-label="Debug">
    {sourceVersion&&<p>{sourceVersion}</p>}
    {savedFinding&&<p>{savedFinding}</p>}
    <label>执行轮次 <select value={attempt} disabled={busy} onChange={event=>setSelection(event.target.value)}>
      {attempts.map(id=><option key={id}>{id}</option>)}
    </select></label>
    <button className="thread-control-button" disabled={busy} onClick={()=>void locate()}>定位首条异常</button>
    {observation?.attempt===attempt&&<p role="status">{observation.text}</p>}
    {allowExport&&<button className="thread-control-button" disabled={busy} onClick={()=>void download()}>下载事件时间线</button>}
    {error&&<p role="alert">{error}</p>}
    <AttemptRecordPanel key={attempt} attemptId={attempt} read={read}/>
  </section>
}
