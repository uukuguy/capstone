import './DebugWorkspace.css'
import {Bug, Download, RefreshCw, ScanSearch} from 'lucide-react'
import {useEffect, useState} from 'react'
import AttemptRecordPanel, {type AttemptRecordReader} from './AttemptRecordPanel'
import MarkdownContent from './MarkdownContent'
import {firstDebugObservation} from './debugObservation'
import type {DebugSnapshotFinding} from './threadHttpTransport'

type SourceRepository = 'capstone' | 'data-gateway'
type ReviewedExport = {diagnosis_markdown: string; reproduction: Record<string, unknown>}
const statusLabels: Record<string, string> = {
  queued:'排队', running:'执行中', completed:'已完成', failed:'失败', cancelled:'已停止', unknown:'结果未知',
}

export default function DebugWorkspace({threadId,attempts,attemptLabel,through,read,allowExport,downloadSession,operatorLoginUrl,readEvidence,readSnapshots,readSnapshotFinding,reviewExport,readHistory,readDiagnosis,readSource,runProbe,savedFinding,sourceVersion,refreshSource}:{
  threadId:string; attempts:string[]; attemptLabel:(id:string)=>string|undefined; through:number; read:AttemptRecordReader; allowExport:boolean; savedFinding:string; sourceVersion:string; refreshSource:()=>void
  readEvidence?: (id?: string, snapshotId?: string) => Promise<string>
  downloadSession?: (streamToFile?: boolean) => Promise<void>
  operatorLoginUrl?: string
  readSnapshots?: (id: string) => Promise<{snapshot_id: string; status: string | null}[]>
  readSnapshotFinding?: (id: string, snapshotId: string) => Promise<DebugSnapshotFinding | null>
  reviewExport?: (id: string, snapshotId: string, review: ReviewedExport | null) => Promise<void>
  readHistory?: () => Promise<{investigation_id: string; objective: string; status: string | null}[]>
  readDiagnosis?: (id: string) => Promise<{answer?: string; status: string; source?: string; finding?: {summary?: string}}>
  readSource?: (id: string, query: URLSearchParams) => Promise<{revision: string; files?: string[]; next_offset?: number | null; lines?: string[]; first_line?: number}>
  runProbe?: (id: string, tool: string, args: Record<string, unknown>) => Promise<unknown>
}){
  const [selection,setSelection]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [streamSave,setStreamSave]=useState(false)
  const [observation,setObservation]=useState<{attempt:string;text:string}|null>(null)
  const [history, setHistory] = useState<Awaited<ReturnType<NonNullable<typeof readHistory>>>>([])
  useEffect(() => {
    if (!readHistory) return
    let current = true
    void readHistory().then(rows => {
      if (current) setHistory(rows)
    }).catch(() => {
      if (current) setError('暂时无法读取补查证据。')
    })
    return () => { current = false }
  }, [readHistory, savedFinding])
  const [diagnosis, setDiagnosis] = useState<{id: string; text: string; source?: string}>()
  const [snapshots, setSnapshots] = useState<{id: string; rows: Awaited<ReturnType<NonNullable<typeof readSnapshots>>>}>()
  const [snapshotId, setSnapshotId] = useState('')
  const [snapshotFinding, setSnapshotFinding] = useState<{id: string; snapshot: string; finding: DebugSnapshotFinding | null}>()
  async function loadSnapshotFinding(id: string, snapshot: string) {
    if (!readSnapshotFinding || busy) return
    setBusy(true)
    setError('')
    try {
      const finding = await readSnapshotFinding(id, snapshot)
      setSnapshotFinding({id, snapshot, finding})
    } catch {
      setError('暂时无法读取阶段结论。')
    } finally { setBusy(false) }
  }
  const [sourcePage, setSourcePage] = useState<{id: string; repository: SourceRepository; revision: string; files: string[]; next: number | null}>()
  const [excerpt, setExcerpt] = useState<{id: string; repository: SourceRepository; path: string; lines: string[]; first: number; citation?: string}>()
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
  async function browseSource(id: string, repository: SourceRepository, offset = 0, path?: string, line = 1, citation?: string, expectedRevision?: string) {
    if (!readSource || busy) return
    setBusy(true)
    setError('')
    if (citation) setExcerpt(undefined)
    try {
      const query = new URLSearchParams({repository, ...(path === undefined ? {offset: String(offset)} : {path, line: String(line)})})
      const result = await readSource(id, query)
      if (expectedRevision !== undefined && result.revision !== expectedRevision) {
        throw new Error('返回的源码版本与快照引用不同。')
      }
      if (path === undefined) {
        setSourcePage({id, repository, revision: result.revision, files: result.files ?? [], next: result.next_offset ?? null})
        setExcerpt(undefined)
      } else {
        setExcerpt({id, repository, path, lines: result.lines ?? [], first: result.first_line ?? line, citation})
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
      setDiagnosis({id, text: result.answer || result.finding?.summary || '此调查尚无诊断结论。', source: result.source})
    } catch { setError('暂时无法读取诊断结果。') }
    finally { setBusy(false) }
  }
  async function downloadEvidence(id: string, savedSnapshot?: string){
    if (!readEvidence || busy) return
    setBusy(true)
    setError('')
    try {
      const snapshot = savedSnapshot || (await readSnapshots?.(id))?.[0]?.snapshot_id
      if (!snapshot) throw new Error('这次补查还没有已保存的证据。')
      const document = await readEvidence(id, snapshot)
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
  async function loadSnapshots(id: string) {
    if (!readSnapshots || busy) return
    setBusy(true)
    setError('')
    try {
      setSnapshots({id, rows: await readSnapshots(id)})
      setSnapshotId('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法读取证据快照。')
    } finally { setBusy(false) }
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

  const digest=sourceVersion.match(/[0-9a-f]{64}/)?.[0]
  const matched=sourceVersion.startsWith('当前网关源码 ')
  return <section className="debug-workspace" aria-label="Debug">
    <header><Bug size={18} aria-hidden="true"/><h3>调试调查</h3></header>
    <section aria-labelledby={`debug-handoff-${threadId}`}>
    <h4 id={`debug-handoff-${threadId}`}>交给研发</h4>
    <p>把当前会话的问答、相关文件和获准外带的执行证据打包交给研发。</p>
    {downloadSession&&<button type="button" disabled={busy} onClick={async ()=>{
      setBusy(true)
      setError('')
      try { await downloadSession(streamSave); setStreamSave(false) }
      catch(cause) {
        if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
          if (cause instanceof Error && cause.name === 'DebugStreamSaveRequired') setStreamSave(true)
          setError(cause instanceof Error ? cause.message : '调试包下载失败。')
        }
      }
      finally { setBusy(false) }
    }}><Download size={15}/>{streamSave?'保存调试包到文件':'下载调试包'}</button>}
    {!downloadSession&&(operatorLoginUrl
      ? <a href={operatorLoginUrl}>以操作员身份登录</a>
      : <p>当前部署未开放调试包下载。</p>)}
    </section>
    <section>
    <h4>现场补查</h4>
    <p>证据不足时，在主会话发送 <code>/debug 核对刚才失败的查询，定位第一个异常阶段</code>。</p>
    <p>进度显示在主会话。保存的结果列在下方，需要交给研发时可重新下载调试包。</p>
    {readHistory&&<button type="button" disabled={busy} onClick={()=>void loadHistory()}>刷新补查证据</button>}
    {history.length===0 ? <p>暂无补查记录。</p> : <ul className="debug-evidence-list">
      {history.map(item=>{
        const open = diagnosis?.id === item.investigation_id
        return <li key={item.investigation_id} className="debug-evidence-item" data-open={open}>
          <div className="debug-evidence-heading">
            <p>{item.objective}</p>
            <span>{statusLabels[item.status ?? ''] ?? '已登记'}</span>
          </div>
          <div className="debug-actions">
            <button type="button" disabled={busy} aria-expanded={open}
              aria-label={`${open ? '收起证据' : '查看证据'} · ${item.objective}`}
              onClick={()=>void selectDiagnosis(open ? '' : item.investigation_id)}>
              {open ? '收起证据' : '查看证据'}
            </button>
            {allowExport&&readEvidence&&<button type="button" disabled={busy}
              aria-label={`下载此证据 · ${item.objective}`}
              onClick={()=>void downloadEvidence(item.investigation_id,open&&snapshots?.id===item.investigation_id ? snapshotId : undefined)}>下载此证据</button>}
          </div>
          {open&&<div className="debug-evidence-detail">
              {diagnosis?.text&&<MarkdownContent>{diagnosis.text}</MarkdownContent>}
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
              {excerpt&&excerpt.id===diagnosis?.id&&!excerpt.citation&&<>
                <pre>{excerpt.lines.map((line,index)=>`${excerpt.first+index}  ${line}`).join('\n')}</pre>
                {excerpt.lines.length===40&&<button type="button" disabled={busy}
                  onClick={()=>void browseSource(excerpt.id,excerpt.repository,0,excerpt.path,excerpt.first+40)}>下一段源码</button>}
              </>}
              {diagnosis&&readSnapshots&&<button type="button" disabled={busy}
                onClick={()=>void loadSnapshots(diagnosis.id)}>查看已保存快照</button>}
              {snapshots?.id===diagnosis?.id&&snapshots&&<label>证据快照
                <select disabled={busy} value={snapshotId} onChange={event=>setSnapshotId(event.target.value)}>
                  <option value="">当前调查状态</option>
                  {snapshots.rows.map(item=><option key={item.snapshot_id} value={item.snapshot_id}>
                    {({queued:'排队', running:'执行中', completed:'已完成', failed:'失败', cancelled:'已停止',
                      unknown:'结果未知'} as Record<string,string>)[item.status ?? ''] ?? '已保存'} · {item.snapshot_id.slice(0,8)}
                  </option>)}
                </select></label>}
              {diagnosis&&snapshots?.id===diagnosis.id&&snapshotId&&readSnapshotFinding&&
                <button type="button" disabled={busy} onClick={()=>void loadSnapshotFinding(diagnosis.id,snapshotId)}>查看阶段结论</button>}
              {snapshotFinding&&snapshots?.id===diagnosis?.id&&snapshotFinding.id===diagnosis?.id&&snapshotFinding.snapshot===snapshotId&&
                <div className="debug-finding">
                  <p>{snapshotFinding.finding?.summary ?? '此快照没有保存阶段结论。'}</p>
                  {snapshotFinding.finding?.next_step&&<p>下一步 · {snapshotFinding.finding.next_step}</p>}
                  {Boolean(snapshotFinding.finding?.event_refs?.length)&&<p>Capstone 事件
                    {' '}{snapshotFinding.finding?.event_refs?.map(seq=><code key={seq}>#{seq}</code>)}
                  </p>}
                  {Boolean(snapshotFinding.finding?.gateway_refs?.length)&&<p>网关回执
                    {' '}{snapshotFinding.finding?.gateway_refs?.map(call=><code key={call}>{call}</code>)}
                  </p>}
                  {snapshotFinding.finding?.source_refs?.map(ref=>{
                    const label = `${ref.repository} ${ref.path}:${ref.line}`
                    const key = `${snapshotId}/${ref.revision}/${label}`
                    return <div key={key} className="debug-source-citation">
                      {readSource ? <button type="button" disabled={busy}
                        onClick={()=>void browseSource(snapshotFinding.id,ref.repository,0,ref.path,ref.line,key,ref.revision)}>
                        {label}
                      </button> : <span>{label}</span>}
                      <code title={ref.revision}>{ref.revision.slice(0,12)}</code>
                      {excerpt?.id===snapshotFinding.id&&excerpt.citation===key&&
                        <pre>{excerpt.lines.map((line,index)=>`${excerpt.first+index}  ${line}`).join('\n')}</pre>}
                    </div>
                  })}
                </div>}
              {allowExport&&reviewExport&&diagnosis&&snapshots?.id===diagnosis.id&&snapshotId&&
                <DebugExportReview key={snapshotId} review={value=>reviewExport(diagnosis.id,snapshotId,value)}/>}
          </div>}
        </li>
      })}
    </ul>}
    {error&&<p role="alert">{error}</p>}</section>
    <section><details><summary>执行详情</summary>
    {attempt?<><label>选择要检查的指令<select value={attempt} disabled={busy} onChange={event=>setSelection(event.target.value)}>
      {attempts.map((id,index)=><option key={id} value={id}>{attemptLabel(id)??(index===0?'最近一次执行':'执行记录 · '+id.slice(-8))}</option>)}
    </select></label>
    <div className="debug-actions"><button type="button" disabled={busy} onClick={()=>void locate()}><ScanSearch size={15}/>查找首条异常</button></div>
    {observation?.attempt===attempt&&<p role="status">{observation.text}</p>}
    <AttemptRecordPanel key={attempt} attemptId={attempt} read={read}/>
    </>:<p>这段会话还没有执行记录。</p>}
    <h4>网关源码</h4><div className="debug-source-status"><span role="status">{matched?'已匹配当前网关版本':sourceVersion.replace(digest??'','').replace('摘要 。','')||'正在核对…'}</span>
    <button type="button" onClick={refreshSource}><RefreshCw size={14}/>重新核对</button></div>
    {digest&&<details><summary>查看版本摘要</summary><code>{digest}</code></details>}</details></section>
  </section>
}

function DebugExportReview({review}:{review:(value: ReviewedExport | null)=>Promise<void>}) {
  const [conclusion,setConclusion]=useState('')
  const [example,setExample]=useState('{}')
  const [busy,setBusy]=useState(false)
  const [status,setStatus]=useState('')
  async function save(approve:boolean) {
    setBusy(true)
    setStatus('')
    try {
      const reproduction: unknown = approve ? JSON.parse(example) : {}
      if (!reproduction || typeof reproduction!=='object' || Array.isArray(reproduction))
        throw new Error('复现数据须为 JSON 对象。')
      await review(approve ? {diagnosis_markdown:conclusion.trim(), reproduction:reproduction as Record<string, unknown>} : null)
      setStatus(approve ? '该快照的外带材料已核准。' : '该快照的外带材料已撤回。')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '暂时无法更新外带审核。')
    } finally {setBusy(false)}
  }
  return <details>
    <summary>审核快照外带材料</summary>
    <p>填写允许交给研发的结论和最小复现数据。网关记录仍按网关策略导出。</p>
    <label>已审阅结论<textarea value={conclusion} onChange={event=>setConclusion(event.target.value)} disabled={busy}/></label>
    <label>复现数据（JSON）<textarea value={example} onChange={event=>setExample(event.target.value)} disabled={busy}/></label>
    <div className="debug-actions">
      <button type="button" disabled={busy||!conclusion.trim()} onClick={()=>void save(true)}>核准外带</button>
      <button type="button" disabled={busy} onClick={()=>void save(false)}>撤回核准</button>
    </div>
    {status&&<p role="status">{status}</p>}
  </details>
}
