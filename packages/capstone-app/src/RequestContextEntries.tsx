import {useEffect,useRef,useState} from 'react'
import {contextCategories,type Category} from './instructionContext'
import {ThreadTransportError} from './threadHttpTransport'

export type ReadRequestContext=(attempt:string,ref:string,index?:number,signal?:AbortSignal,credential?:string)=>Promise<unknown>
type Origin={kind:'file'|'skill'|'compaction';id:string;revision:string;delivery:string;offset?:number;length?:number}
type Entry={origin?:Origin;digest?:string;index:number;carrier:Category;role:string;name?:string;source_id?:string;truncated?:boolean;redacted?:boolean}
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
    const source:Origin|undefined=(origin.kind==='file'||origin.kind==='skill'||origin.kind==='compaction')&&typeof origin.id==='string'
      &&typeof origin.revision==='string'&&typeof origin.delivery==='string'
      ? {kind:origin.kind,id:origin.id,revision:origin.revision,delivery:origin.delivery,
        offset:typeof origin.offset==='number'?origin.offset:undefined,length:typeof origin.length==='number'?origin.length:undefined}
      :undefined
    return {origin:source,index:row.index,carrier:row.carrier as Category,role:row.role,name:typeof row.name==='string'?row.name:undefined,
      digest:typeof row.digest==='string'&&/^[a-f0-9]{64}$/.test(row.digest)?row.digest:undefined,
      source_id:typeof row.source_id==='string'?row.source_id:undefined,truncated:row.truncated===true,redacted:row.redacted===true}
  })
  return {entries,total_entries:Number(raw.total_entries),modelId:typeof raw.model_id==='string'?raw.model_id:undefined}
}

function entryTitle(entry:Entry) {
  const label=roles[entry.role]??contextCategories[entry.carrier]
  return entry.name?`${label} · ${entry.name}`:label
}

function compareEntries(before:Entry[],after:Entry[]) {
  const remaining=[...before]
  const added:Entry[]=[],changed:Entry[]=[]
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
    if(match>=0){remaining.splice(match,1);added.splice(i,1);changed.unshift(entry)}
  }
  return {added,removed:remaining,changed}
}

export default function RequestContextEntries({attempt,snapshot,previous,category,read,credential,onCredential,onResetCategory}:{
  attempt:string;snapshot:string;previous?:string;category?:Category;read:ReadRequestContext;credential?:string;onCredential:(value:string)=>void;onResetCategory?:()=>void
}){
  const [visibleLimit,setVisibleLimit]=useState(16)
  const [document,setDocument]=useState<Snapshot>()
  const [selected,setSelected]=useState<number>()
  const [text,setText]=useState<string>()
  const [requiresCredential,setRequiresCredential]=useState(false)
  const [status,setStatus]=useState('')
  const [sourceKind,setSourceKind]=useState<Origin['kind']>()
  const [earlier,setEarlier]=useState<Snapshot>()
  const pending=useRef<AbortController>(undefined)
  useEffect(()=>()=>pending.current?.abort(),[])

  async function load(index?:number,access=credential) {
    pending.current?.abort()
    const controller=new AbortController()
    pending.current=controller
    setSelected(index)
    setText(undefined)
    setStatus('正在读取…')
    try {
      const result=await read(attempt,snapshot,index,controller.signal,access)
      if(controller.signal.aborted)return
      if(index===undefined)setDocument(snapshotIndex(result))
      else {
        const entry=asObject(asObject(result).entry)
        if(entry.index!==index||typeof entry.text!=='string')throw new Error('请求正文无效')
        setText(entry.text)
      }
      setRequiresCredential(false)
      setStatus('')
    } catch(error) {
      if(controller.signal.aborted)return
      const denied=error instanceof ThreadTransportError&&(error.status===403||error.status===401)
      setRequiresCredential(denied)
      setStatus(denied
        ? '需要当前工作区的操作员凭据才能读取请求正文。'
        : '请求正文暂时无法读取。')
    }
  }
  async function compare() {
    if(!previous)return
    pending.current?.abort()
    const controller=new AbortController()
    pending.current=controller
    setStatus('正在读取上一请求…')
    try {
      const result=await read(attempt,previous,undefined,controller.signal,credential)
      if(controller.signal.aborted)return
      setEarlier(snapshotIndex(result))
      setStatus('')
    } catch {
      if(!controller.signal.aborted)setStatus('上一请求暂时无法读取。')
    }
  }
  const comparison=document&&earlier?compareEntries(earlier.entries,document.entries):undefined
  const entries=document?.entries.filter(entry=>(!category||entry.carrier===category)&&(!sourceKind||entry.origin?.kind===sourceKind))??[]
  return <section className="context-request-entries" aria-label="实际请求正文">
    <div className="context-section-title">
      <h4>实际请求正文</h4>
      {document&&category&&<button type="button" onClick={onResetCategory}>显示全部分类</button>}
      {!document&&<button type="button" onClick={()=>void load()}>读取诊断记录</button>}
    </div>
    {status&&<p role="status">{status}</p>}
    {requiresCredential&&<form className="context-credential-form" onSubmit={event=>{
      event.preventDefault()
      const value=String(new FormData(event.currentTarget).get('credential')??'').trim()
      if(!value)return
      onCredential(value)
      event.currentTarget.reset()
      void load(selected,value)
    }}>
      <label>操作员凭据<input name="credential" type="password" autoComplete="off" required/></label>
      <button type="submit">读取</button>
    </form>}
    {document&&<>
      <small>{document.modelId&&`${document.modelId} · `}已采集 {document.entries.length} / {document.total_entries} 项，按发送顺序</small>
      {previous&&<button className="context-show-items" type="button" onClick={()=>void compare()}>对比上一次请求</button>}
      {comparison&&<details className="context-request-diff" open>
        <summary>已采集内容变化 · 新增 {comparison.added.length} · 移除 {comparison.removed.length} · 改写 {comparison.changed.length}</summary>
        {(['added','removed','changed'] as const).map(kind=>comparison[kind].length>0&&<ul key={kind}>
          {comparison[kind].map(entry=><li key={entry.index}>{({added:'新增',removed:'移除',changed:'改写'})[kind]} · {entryTitle(entry)}</li>)}
        </ul>)}
      </details>}
      <div className="context-source-filters" aria-label="按来源筛选">
        {([...new Set(document.entries.flatMap(entry=>entry.origin?[entry.origin.kind]:[]))]).map(kind=>
          <button type="button" key={kind} aria-pressed={sourceKind===kind}
            onClick={()=>setSourceKind(sourceKind===kind?undefined:kind)}>{kind==='file'?'文件来源':kind==='skill'?'技能来源':'压缩摘要'}</button>)}
      </div>
      {!entries.length&&<p>所选分类没有已采集条目。</p>}
      <ol className="context-content-items">
        {entries.slice(0,visibleLimit).map(entry=><li key={entry.index}>
          <button className="context-entry-open" type="button" aria-expanded={selected===entry.index} onClick={()=>void load(entry.index)}>
            <i className="context-category-dot" data-category={entry.carrier}/>
            <span>{entry.index} · {entryTitle(entry)}</span>
            {(entry.redacted||entry.truncated)&&<small>{[entry.redacted?'已遮蔽':'',entry.truncated?'已截断':''].filter(Boolean).join(' · ')}</small>}
          </button>
          {selected===entry.index&&<div className="context-entry-body">
            {entry.origin&&<p className="context-entry-origin">
              {entry.origin.kind==='file'?'文件':entry.origin.kind==='skill'?'技能':'压缩摘要'} {entry.origin.id} · {entry.origin.revision}
              {entry.origin.offset!==undefined&&entry.origin.length!==undefined&&
                ` · 字节 ${entry.origin.offset}–${entry.origin.offset+entry.origin.length}（${entry.origin.delivery==='reference'?'范围引用':'预览'}）`}
            </p>}
            {entry.source_id&&<small>{entry.carrier==='system'?'组装来源':'工具调用'} {entry.source_id}</small>}
            {text!==undefined&&<pre>{text}</pre>}
          </div>}
        </li>)}
      </ol>
      {entries.length>visibleLimit&&<button type="button" className="context-show-items" onClick={()=>setVisibleLimit(value=>value+16)}>显示更多条目</button>}
    </>}
  </section>
}
