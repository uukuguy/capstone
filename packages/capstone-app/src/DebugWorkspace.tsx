import {useState} from 'react'
import AttemptRecordPanel, {type AttemptRecordReader} from './AttemptRecordPanel'

export default function DebugWorkspace({threadId,attempts,read,allowExport,readTimeline}:{
  threadId:string; attempts:string[]; read:AttemptRecordReader; allowExport:boolean
  readTimeline:(attempt:string,after:number,through?:number)=>Promise<{events:{seq:number;type:string}[];hasMore:boolean;nextAfter:number;through:number}>
}){
  const [selection,setSelection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const attempt=attempts.includes(selection)?selection:attempts[0]
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
  if(!attempt)return <p>当前会话还没有执行记录。</p>
  return <section aria-label="Debug">
    <label>执行轮次 <select value={attempt} disabled={busy} onChange={event=>setSelection(event.target.value)}>
      {attempts.map(id=><option key={id}>{id}</option>)}
    </select></label>
    {allowExport&&<button className="thread-control-button" disabled={busy} onClick={()=>void download()}>{busy?'正在整理记录…':'下载事件时间线'}</button>}
    {error&&<p role="alert">{error}</p>}
    <AttemptRecordPanel key={attempt} attemptId={attempt} read={read}/>
  </section>
}
