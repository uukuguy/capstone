import './DebugWorkspace.css'
import {Bug, Download, RefreshCw, ScanSearch} from 'lucide-react'
import {useState} from 'react'
import AttemptRecordPanel, {type AttemptRecordReader} from './AttemptRecordPanel'
import {firstDebugObservation} from './debugObservation'

export default function DebugWorkspace({threadId,attempts,attemptLabel,through,read,allowExport,readTimeline,readEvidence,savedFinding,sourceVersion,refreshSource}:{
  threadId:string; attempts:string[]; attemptLabel:(id:string)=>string|undefined; through:number; read:AttemptRecordReader; allowExport:boolean; savedFinding:string; sourceVersion:string; refreshSource:()=>void
  readTimeline:(attempt:string,after:number,through?:number)=>Promise<{events:{seq:number;type:string}[];hasMore:boolean;nextAfter:number;through:number}>
  readEvidence?: () => Promise<unknown>
}){
  const [selection,setSelection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [observation,setObservation]=useState<{attempt:string;text:string}|null>(null)
  const attempt=attempts.includes(selection)?selection:attempts[0]
  async function downloadEvidence(){
    if (!readEvidence || busy) return
    setBusy(true)
    setError('')
    try {
      const document = await readEvidence()
      const url = URL.createObjectURL(new Blob([JSON.stringify(document, null, 2)], {type:'application/json'}))
      const link = window.document.createElement('a')
      link.href = url
      link.download = 'debug-evidence.json'
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法下载调查记录。')
    } finally {
      setBusy(false)
    }
  }
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
  const digest=sourceVersion.match(/[0-9a-f]{64}/)?.[0]
  const matched=sourceVersion.startsWith('当前网关源码 ')
  return <section className="debug-workspace" aria-label="Debug">
    <header><Bug size={18} aria-hidden="true"/><h3>会话调试</h3></header>
    <p>在主会话输入 <code>/debug</code> 和问题，例如「/debug 刚才的请求为什么失败？」。这里可以查阅和下载执行记录。</p>
    <section><h4>执行记录</h4>
    {attempt?<><label>选择要检查的指令<select value={attempt} disabled={busy} onChange={event=>setSelection(event.target.value)}>
      {attempts.map((id,index)=><option key={id} value={id}>{attemptLabel(id)??(index===0?'最近一次执行':'执行记录 · '+id.slice(-8))}</option>)}
    </select></label>
    <div className="debug-actions"><button type="button" disabled={busy} onClick={()=>void locate()}><ScanSearch size={15}/>查找首条异常</button>
    {allowExport&&<button type="button" disabled={busy} onClick={()=>void download()}><Download size={15}/>下载时间线</button>}</div>
    {observation?.attempt===attempt&&<p role="status">{observation.text}</p>}
    <AttemptRecordPanel key={attempt} attemptId={attempt} read={read}/>
    </>:<p>这段会话还没有执行记录。</p>}
    {savedFinding&&<p>{savedFinding}</p>}
    {allowExport&&readEvidence&&<button type="button" disabled={busy} onClick={()=>void downloadEvidence()}>下载当前调查记录</button>}
    {error&&<p role="alert">{error}</p>}</section>
    <section><h4>网关源码</h4><div className="debug-source-status"><span role="status">{matched?'已匹配当前网关版本':sourceVersion.replace(digest??'','').replace('摘要 。','')||'正在核对…'}</span>
    <button type="button" onClick={refreshSource}><RefreshCw size={14}/>重新核对</button></div>
    {digest&&<details><summary>查看版本摘要</summary><code>{digest}</code></details>}</section>
  </section>
}
