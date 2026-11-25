import './DebugWorkspace.css'
import {Bug, Download, RefreshCw, ScanSearch} from 'lucide-react'
import {useState} from 'react'
import AttemptRecordPanel, {type AttemptRecordReader} from './AttemptRecordPanel'
import MarkdownContent from './MarkdownContent'
import {firstDebugObservation} from './debugObservation'

type SourceRepository = 'capstone' | 'data-gateway'

export default function DebugWorkspace({threadId,attempts,attemptLabel,through,read,allowExport,readTimeline,readEvidence,readHistory,readDiagnosis,readSource,runProbe,savedFinding,sourceVersion,refreshSource}:{
  threadId:string; attempts:string[]; attemptLabel:(id:string)=>string|undefined; through:number; read:AttemptRecordReader; allowExport:boolean; savedFinding:string; sourceVersion:string; refreshSource:()=>void
  readTimeline:(attempt:string,after:number,through?:number)=>Promise<{events:{seq:number;type:string}[];hasMore:boolean;nextAfter:number;through:number}>
  readEvidence?: (id?: string) => Promise<string>
  readHistory?: () => Promise<{investigation_id: string; objective: string; status: string | null}[]>
  readDiagnosis?: (id: string) => Promise<{answer?: string; status: string; source?: string}>
  readSource?: (id: string, query: URLSearchParams) => Promise<{revision: string; files?: string[]; next_offset?: number | null; lines?: string[]; first_line?: number}>
  runProbe?: (id: string, tool: string, args: Record<string, unknown>) => Promise<unknown>
}){
  const [selection,setSelection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [observation,setObservation]=useState<{attempt:string;text:string}|null>(null)
  const [history, setHistory] = useState<Awaited<ReturnType<NonNullable<typeof readHistory>>>>([])
  const [diagnosis, setDiagnosis] = useState<{id: string; text: string; source?: string}>()
  const [sourcePage, setSourcePage] = useState<{id: string; repository: SourceRepository; revision: string; files: string[]; next: number | null}>()
  const [excerpt, setExcerpt] = useState<{id: string; repository: SourceRepository; path: string; lines: string[]; first: number}>()
  const [probeTool, setProbeTool] = useState('')
  const [probeArgs, setProbeArgs] = useState('{}')
  const [probe, setProbe] = useState<{id: string; receipt: unknown}>()
  async function verifyReadOnly(id: string) {
    if (!runProbe || busy) return
    setBusy(true)
    setError('')
    try {
      const tool = probeTool.trim()
      const args: unknown = JSON.parse(probeArgs)
      if (!tool || !args || typeof args !== 'object' || Array.isArray(args)) {
        throw new Error('请输入工具名和 JSON 参数对象。')
      }
      setProbe(undefined)
      const receipt = await runProbe(id, tool, args as Record<string, unknown>)
      setProbe({id, receipt})
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法读取复验回执。')
    } finally { setBusy(false) }
  }
  async function browseSource(id: string, repository: SourceRepository, offset = 0, path?: string, line = 1) {
    if (!readSource || busy) return
    setBusy(true)
    setError('')
    try {
      const query = new URLSearchParams({repository, ...(path === undefined ? {offset: String(offset)} : {path, line: String(line)})})
      const result = await readSource(id, query)
      if (path === undefined) {
        setSourcePage({id, repository, revision: result.revision, files: result.files ?? [], next: result.next_offset ?? null})
        setExcerpt(undefined)
      } else {
        setExcerpt({id, repository, path, lines: result.lines ?? [], first: result.first_line ?? line})
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '历史源码暂不可读。')
    } finally { setBusy(false) }
  }
  const attempt=attempts.includes(selection)?selection:attempts[0]
  async function loadHistory(){
    if (!readHistory) return
    setError('')
    try { setHistory(await readHistory()) }
    catch { setError('暂时无法读取调查历史。') }
  }
  async function selectDiagnosis(id: string){
    if (!id) { setDiagnosis(undefined); return }
    if (!readDiagnosis) return
    setBusy(true)
    setError('')
    try {
      const result = await readDiagnosis(id)
      setDiagnosis({id, text: result.answer || '此调查尚无诊断结论。', source: result.source})
    } catch { setError('暂时无法读取诊断结果。') }
    finally { setBusy(false) }
  }
  async function downloadEvidence(){
    if (!readEvidence || busy) return
    setBusy(true)
    setError('')
    try {
      const document = await readEvidence(diagnosis?.id)
      const url = URL.createObjectURL(new Blob([document], {type:'application/json'}))
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
    {readHistory&&<button type="button" disabled={busy} onClick={()=>void loadHistory()}>查看调查历史</button>}
    {history.length>0&&<label>调查<select disabled={busy} value={diagnosis?.id ?? ''} onChange={event=>void selectDiagnosis(event.target.value)}>
      <option value="">最新调查</option>
      {history.map(item=><option key={item.investigation_id} value={item.investigation_id}>{item.objective}</option>)}
    </select></label>}
    {(diagnosis?.text || savedFinding)&&<MarkdownContent>{diagnosis?.text || savedFinding}</MarkdownContent>}
    {diagnosis?.source&&<p>{diagnosis.source}</p>}
    {diagnosis&&runProbe&&<details>
      <summary>只读网关复验</summary>
      <label>工具名<input value={probeTool} disabled={busy} onChange={event=>setProbeTool(event.target.value)}/></label>
      <label>参数（JSON）<textarea value={probeArgs} disabled={busy} onChange={event=>setProbeArgs(event.target.value)}/></label>
      <button type="button" disabled={busy||!probeTool.trim()} onClick={()=>void verifyReadOnly(diagnosis.id)}>执行或查回原复验</button>
      {probe?.id===diagnosis.id&&probe.receipt!==undefined&&<pre>{JSON.stringify(probe.receipt,null,2)}</pre>}
    </details>}
    {diagnosis&&readSource&&<div className="debug-actions">
      <button type="button" disabled={busy} onClick={()=>void browseSource(diagnosis.id,'capstone')}>查看历史 Capstone 源码</button>
      <button type="button" disabled={busy} onClick={()=>void browseSource(diagnosis.id,'data-gateway')}>查看历史网关源码</button>
    </div>}
    {sourcePage&&sourcePage.id===diagnosis?.id&&<>
      <p>{sourcePage.repository} <code>{sourcePage.revision}</code></p>
      <label>历史源码文件<select disabled={busy} value={excerpt?.id===sourcePage.id?excerpt.path:''}
        onChange={event=>{if(event.target.value)void browseSource(sourcePage.id,sourcePage.repository,0,event.target.value)}}>
        <option value="">选择文件</option>
        {sourcePage.files.map(path=><option key={path}>{path}</option>)}
      </select></label>
      {sourcePage.next!==null&&<button type="button" disabled={busy}
        onClick={()=>void browseSource(sourcePage.id,sourcePage.repository,sourcePage.next ?? 0)}>下一页文件</button>}
    </>}
    {excerpt&&excerpt.id===diagnosis?.id&&<>
      <pre>{excerpt.lines.map((line,index)=>`${excerpt.first+index}  ${line}`).join('\n')}</pre>
      {excerpt.lines.length===40&&<button type="button" disabled={busy}
        onClick={()=>void browseSource(excerpt.id,excerpt.repository,0,excerpt.path,excerpt.first+40)}>下一段源码</button>}
    </>}
    {allowExport&&readEvidence&&<button type="button" disabled={busy} onClick={()=>void downloadEvidence()}>下载调查记录</button>}
    {error&&<p role="alert">{error}</p>}</section>
    <section><h4>网关源码</h4><div className="debug-source-status"><span role="status">{matched?'已匹配当前网关版本':sourceVersion.replace(digest??'','').replace('摘要 。','')||'正在核对…'}</span>
    <button type="button" onClick={refreshSource}><RefreshCw size={14}/>重新核对</button></div>
    {digest&&<details><summary>查看版本摘要</summary><code>{digest}</code></details>}</section>
  </section>
}
