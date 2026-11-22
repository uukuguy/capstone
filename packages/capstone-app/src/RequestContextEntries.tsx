import {useEffect,useEffectEvent,useRef,useState} from 'react'
import {ChevronRight,GitCompareArrows} from 'lucide-react'
import RequestContextBody from './RequestContextBody'
import {contextCategories,type Category} from './instructionContext'
import {ThreadTransportError} from './threadHttpTransport'

export type ReadRequestContext=(attempt:string,ref:string,index?:number,signal?:AbortSignal)=>Promise<unknown>
const originLabels={file:'文件',skill:'技能',compaction:'压缩摘要',history:'会话历史',handoff:'任务交接',observation:'依赖观察',runtime:'运行环境'} as const
type Origin={kind:keyof typeof originLabels;id:string;revision:string;delivery:string;offset?:number;length?:number}
type Entry={messageIndex?:number;preview?:string;origin?:Origin;digest?:string;index:number;carrier:Category;role:string;name?:string;source_id?:string;truncated?:boolean;redacted?:boolean}
type Snapshot={entries:Entry[];total_entries:number;modelId?:string}
const roles:Record<string,string>={system:'系统提示',definition:'工具定义',user:'用户消息',assistant:'模型消息',toolCall:'工具调用参数',toolResult:'工具返回',unsupported:'结构或媒体块',other:'其他消息'}

function asObject(value:unknown):Record<string,unknown> {
  return value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{}
}

function snapshotIndex(value:unknown):Snapshot {
  const raw=asObject(value)
  if(raw.schema!=='capstone-model-context-snapshot/1'||!Array.isArray(raw.entries)||!Number.isSafeInteger(raw.total_entries))
    throw new Error('请求正文索引无效')
  const entries:Entry[]=raw.entries.map(value=>{
    const row=asObject(value)
    const origin=asObject(row.origin)
    if(typeof row.carrier!=='string'||!Object.hasOwn(contextCategories,row.carrier)||typeof row.index!=='number'||typeof row.role!=='string')
      throw new Error('请求正文条目无效')
    const source:Origin|undefined=(typeof origin.kind==='string'&&Object.hasOwn(originLabels,origin.kind))&&typeof origin.id==='string'
      &&typeof origin.revision==='string'&&typeof origin.delivery==='string'
      ? {kind:origin.kind as Origin['kind'],id:origin.id,revision:origin.revision,delivery:origin.delivery,
        offset:typeof origin.offset==='number'?origin.offset:undefined,length:typeof origin.length==='number'?origin.length:undefined}
      :undefined
    return {origin:source,messageIndex:typeof row.message_index==='number'?row.message_index:undefined,
      preview:typeof row.preview==='string'?row.preview:undefined,index:row.index,carrier:row.carrier as Category,role:row.role,name:typeof row.name==='string'?row.name:undefined,
      digest:typeof row.digest==='string'&&/^[a-f0-9]{64}$/.test(row.digest)?row.digest:undefined,
      source_id:typeof row.source_id==='string'?row.source_id:undefined,truncated:row.truncated===true,redacted:row.redacted===true}
  })
  return {entries,total_entries:Number(raw.total_entries),modelId:typeof raw.model_id==='string'?raw.model_id:undefined}
}

function entryTitle(entry:Entry) {
  const label=roles[entry.role]??contextCategories[entry.carrier]
  return entry.name?`${label} · ${entry.name}`:label
}

function rowTitle(entry:Entry) {
  return entry.origin?originLabels[entry.origin.kind]:entry.name??entryTitle(entry)
}

type Difference={kind:'added'|'removed'|'changed';before?:Entry;after?:Entry}
const differenceLabels={added:'新增',removed:'移除',changed:'改写'} as const

function readBody(result:unknown,index:number) {
  const entry=asObject(asObject(result).entry)
  if(entry.index!==index||typeof entry.text!=='string')throw new Error('请求正文无效')
  return entry.text
}

function entryKey(entry:Entry,snapshot:string) {
  return JSON.stringify([entry.index,entry.digest??snapshot,entry.carrier,entry.role,
    entry.messageIndex,entry.name,entry.source_id,entry.origin,entry.truncated,entry.redacted])
}

function compareEntries(before:Entry[],after:Entry[]) {
  const remaining=[...before]
  const added:Entry[]=[],changed:Difference[]=[]
  for(const entry of after){
    const match=remaining.findIndex(other=>entry.digest!==undefined&&entry.digest===other.digest
      &&entry.carrier===other.carrier&&entry.role===other.role&&entry.name===other.name)
    if(match>=0)remaining.splice(match,1)
    else added.push(entry)
  }
  for(let i=added.length-1;i>=0;i--){
    const entry=added[i]
    const match=remaining.findIndex(other=>other.carrier===entry.carrier&&other.role===entry.role&&(
      entry.source_id!==undefined&&entry.source_id===other.source_id ||
      entry.role==='definition'&&entry.name!==undefined&&entry.name===other.name ||
      entry.role==='system'&&before.filter(row=>row.role==='system').length===1&&after.filter(row=>row.role==='system').length===1
    ))
    if(match>=0){
      const [prior]=remaining.splice(match,1)
      added.splice(i,1)
      changed.unshift({kind:'changed',before:prior,after:entry})
    }
  }
  return {added:added.map((after):Difference=>({kind:'added',after})),
    removed:remaining.map((before):Difference=>({kind:'removed',before})),changed}
}

function DifferenceBody({label,attempt,refId,entry,read}:{label:string;attempt:string;refId:string;entry:Entry;read:ReadRequestContext}) {
  const [body,setBody]=useState<string>()
  const [error,setError]=useState(false)
  useEffect(()=>{
    const controller=new AbortController()
    void read(attempt,refId,entry.index,controller.signal).then(value=>{
      if(!controller.signal.aborted)setBody(readBody(value,entry.index))
    }).catch(()=>{
      if(!controller.signal.aborted)setError(true)
    })
    return ()=>controller.abort()
  },[attempt,refId,entry.index,read])
  return <div className="context-diff-version">
    <div className="context-diff-version-label">{label} · 第 {entry.index} 项</div>
    {entry.truncated&&<small>正文已截断</small>}
    {entry.redacted&&<small>正文包含遮蔽内容</small>}
    {body!==undefined?<RequestContextBody text={body}/>:<p role="status">{error?'正文暂时无法读取。':'正在读取正文…'}</p>}
  </div>
}

function DifferenceRow({difference,attempt,previous,snapshot,read}:{difference:Difference;attempt:string;previous:string;snapshot:string;read:ReadRequestContext}) {
  const [open,setOpen]=useState(false)
  const entry=difference.after??difference.before
  if(!entry)return null
  const title=entry.origin?rowTitle(entry):entryTitle(entry)
  return <li><details className="capstone-call-tool context-entry" open={open}>
    <summary className="context-entry-open" role="button" aria-label={`${differenceLabels[difference.kind]} · ${title}`} aria-expanded={open}
      onClick={event=>{event.preventDefault();setOpen(!open)}}>
      <ChevronRight aria-hidden="true"/><small>{differenceLabels[difference.kind]} · </small>
      <strong className="context-entry-title">{title}</strong>
    </summary>
    {open&&<div className="capstone-call-tool-detail context-entry-body context-diff-bodies">
      {difference.before&&<DifferenceBody label="上一请求" attempt={attempt} refId={previous} entry={difference.before} read={read}/>}
      {difference.after&&<DifferenceBody label="本次请求" attempt={attempt} refId={snapshot} entry={difference.after} read={read}/>}
    </div>}
  </details></li>
}

export default function RequestContextEntries({attempt,snapshot,previous,category,read,onResetCategory,onIndexReady,onIndexUnavailable}:{
  attempt:string;snapshot:string;previous?:string;category?:Category;read:ReadRequestContext;onResetCategory?:()=>void;onIndexReady?:()=>void;onIndexUnavailable?:()=>void
}){
  const [loaded,setLoaded]=useState<{snapshot:string;document:Snapshot}>()
  const [selected,setSelected]=useState<string>()
  const [text,setText]=useState<string>()
  const [status,setStatus]=useState('')
  const [indexStatus,setIndexStatus]=useState('')
  const [comparisonOpen,setComparisonOpen]=useState(false)
  const [comparisonStatus,setComparisonStatus]=useState('')
  const comparisonRequest=useRef<AbortController>(undefined)
  const [earlier,setEarlier]=useState<Snapshot>()
  const pending=useRef<AbortController>(undefined)
  const loadIndex=useEffectEvent((signal:AbortSignal)=>{
    setIndexStatus('正在更新请求索引…')
    void read(attempt,snapshot,undefined,signal).then(value=>{
      if(signal.aborted)return
      const document=snapshotIndex(value)
      setLoaded({snapshot,document})
      setIndexStatus('')
      onIndexReady?.()
    }).catch(error=>{
      if(signal.aborted)return
      pending.current?.abort()
      setLoaded(undefined)
      setSelected(undefined)
      setText(undefined)
      setStatus('')
      onIndexUnavailable?.()
      setIndexStatus(error instanceof ThreadTransportError&&(error.status===403||error.status===401)
        ?'当前入口无法查看受保护正文。下方仍可查看用量摘要。'
        :'请求正文暂时无法读取。')
    })
  })
  useEffect(()=>{
    const controller=new AbortController()
    loadIndex(controller.signal)
    setEarlier(undefined)
    setComparisonOpen(false)
    setComparisonStatus('')
    return ()=>{controller.abort();comparisonRequest.current?.abort()}
  },[attempt,snapshot])
  useEffect(()=>()=>pending.current?.abort(),[])

  async function load(entry:Entry) {
    if(!loaded)return
    const key=entryKey(entry,loaded.snapshot)
    pending.current?.abort()
    const controller=new AbortController()
    pending.current=controller
    setSelected(key===selected?undefined:key)
    setText(undefined)
    if(key===selected){setStatus('');return}
    setStatus('正在读取…')
    try {
      const result=await read(attempt,loaded.snapshot,entry.index,controller.signal)
      if(controller.signal.aborted)return
      setText(readBody(result,entry.index))
      setStatus('')
    } catch(error) {
      if(controller.signal.aborted)return
      const denied=error instanceof ThreadTransportError&&(error.status===403||error.status===401)
      setStatus(denied
        ? '当前入口无法查看受保护正文。下方仍可查看用量摘要。'
        : '请求正文暂时无法读取。')
    }
  }
  async function toggleComparison() {
    if(!previous)return
    if(comparisonOpen){
      comparisonRequest.current?.abort()
      setComparisonOpen(false)
      return
    }
    setComparisonOpen(true)
    if(earlier)return
    const controller=new AbortController()
    comparisonRequest.current=controller
    setComparisonStatus('正在读取上一请求…')
    try {
      const result=await read(attempt,previous,undefined,controller.signal)
      if(controller.signal.aborted)return
      setEarlier(snapshotIndex(result))
      setComparisonStatus('')
    } catch {
      if(!controller.signal.aborted)setComparisonStatus('上一请求暂时无法读取。')
    }
  }
  const document=loaded?.document
  const currentIndex=loaded?.snapshot===snapshot
  const comparison=currentIndex&&document&&earlier?compareEntries(earlier.entries,document.entries):undefined
  const entries=document?.entries.filter(entry=>!category||entry.carrier===category)??[]
  const toolCalls=new Map(document?.entries.flatMap(entry=>
    entry.role==='toolCall'&&entry.source_id?[[entry.source_id,entry.index] as const]:[]))
  const renderEntry=(entry:Entry)=>{
    const key=entryKey(entry,loaded?.snapshot??snapshot)
    const open=selected===key
    return <li key={key}><details className="capstone-call-tool context-entry" open={open}>
          <summary className="context-entry-open" role="button" aria-label={`${entry.index} ${rowTitle(entry)}`} aria-expanded={open}
            onClick={event=>{event.preventDefault();void load(entry)}}>
            <ChevronRight aria-hidden="true"/>
            <small className="context-entry-index">{entry.index}</small>
            <i className="context-category-dot" data-category={entry.carrier} aria-hidden="true"/>
            <strong className="context-entry-title" title={entry.origin?.id??entryTitle(entry)}>
              {rowTitle(entry)}
            </strong>
            {(entry.origin||entry.name)&&<small className="context-entry-role">{roles[entry.role]??contextCategories[entry.carrier]}</small>}
            {entry.role==='toolResult'&&entry.source_id&&toolCalls.has(entry.source_id)&&
              <small className="context-entry-role">调用 #{toolCalls.get(entry.source_id)}</small>}
            {(entry.redacted||entry.truncated)&&<small className="context-entry-state">{[entry.redacted?'已遮蔽':'',entry.truncated?'已截断':''].filter(Boolean).join(' · ')}</small>}
            {entry.preview&&!open&&<span className="context-message-preview">{entry.preview}</span>}
          </summary>
          {open&&<div className="capstone-call-tool-detail context-entry-body">
            {entry.origin&&<p className="context-entry-origin">
              {entry.origin.id} · {entry.origin.revision}
              {entry.origin.offset!==undefined&&entry.origin.length!==undefined&&
                ` · 字节 ${entry.origin.offset}–${entry.origin.offset+entry.origin.length}（${entry.origin.delivery==='reference'?'范围引用':'预览'}）`}
            </p>}
            {entry.source_id&&<small>{entry.carrier==='system'?'组装来源':'工具调用 ID'} {entry.source_id}</small>}
            {text!==undefined&&<RequestContextBody text={text}/>}
          </div>}
        </details></li>
  }
  return <section className="context-request-entries" aria-label="实际请求正文">
    <div className="context-section-title">
      <h4>实际请求正文</h4>
      <div className="context-request-actions">
        {document&&category&&<button type="button" onClick={onResetCategory}>显示全部分类</button>}
        {currentIndex&&previous&&<button className="context-compare-action" type="button" aria-pressed={comparisonOpen}
          title="与上一请求对比" onClick={()=>void toggleComparison()}>
          <GitCompareArrows size={14} aria-hidden="true"/>对比上一请求
        </button>}
      </div>
    </div>
    {!document&&indexStatus&&<p role="status">{indexStatus}</p>}
    {status&&document?.entries.some(entry=>entryKey(entry,loaded!.snapshot)===selected)&&<p role="status">{status}</p>}
    {document&&<>
      <small>{!currentIndex&&'正在更新 · '}{document.modelId&&`${document.modelId} · `}已采集 {document.entries.length} / {document.total_entries} 项，按 SDK 输入顺序</small>
      {comparisonOpen&&<section className="context-request-diff capstone-call-tool-detail" aria-label="与上一请求的差异">
        {comparisonStatus&&<p role="status">{comparisonStatus}</p>}
        {comparison&&previous&&<>
          <p><strong>与上一请求的差异</strong><small>新增 {comparison.added.length} · 移除 {comparison.removed.length} · 改写 {comparison.changed.length}</small></p>
          {(['added','removed','changed'] as const).map(kind=>comparison[kind].length>0&&<ul key={kind}>
            {comparison[kind].map(difference=><DifferenceRow key={difference.after?.index??difference.before?.index}
              difference={difference} attempt={attempt} previous={previous} snapshot={snapshot} read={read}/>)}
          </ul>)}
        </>}
      </section>}
      {!entries.length&&<p>所选分类没有已采集条目。</p>}
      {(['system','tools'] as const).map(carrier=>{
        const group=entries.filter(entry=>entry.carrier===carrier)
        return group.length>0&&<details key={carrier} className="context-input-group" open={category===carrier||undefined}>
          <summary>{contextCategories[carrier]} <small>{group.length} 项</small></summary>
          <ol className="context-content-items context-request-trace">{group.map(renderEntry)}</ol>
        </details>
      })}
      {entries.some(entry=>entry.carrier==='messages'||entry.carrier==='tool_results')&&<>
        <h4 className="context-input-messages">消息列表</h4>
        <ol className="context-content-items context-request-trace">{entries
          .filter(entry=>entry.carrier==='messages'||entry.carrier==='tool_results')
          .reduce<Entry[][]>((groups,entry)=>{
            const group=groups.at(-1)
            if(group&&entry.messageIndex!==undefined&&group[0].messageIndex===entry.messageIndex)group.push(entry)
            else groups.push([entry])
            return groups
          },[]).map(group=>group[0].messageIndex===undefined
            ?renderEntry(group[0])
            :<li className="context-input-message" key={`message:${group[0].messageIndex}:${group[0].index}`}>
              <small>消息 {group[0].messageIndex}</small>
              <ol>{group.map(renderEntry)}</ol>
            </li>)}</ol>
      </>}
    </>}
  </section>
}
