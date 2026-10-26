import {useEffect,useMemo,useRef,useState} from 'react'
import type {HttpThreadTransport} from './threadHttpTransport'
import {parseThreadDisplayRequest,type ThreadElectricalViewRequest} from './threadViewRouting'
import {loadElectricalModelView,parseElectricalViewOpen,parseElectricalViewPage,parseElectricalViewFailure,
  type ElectricalViewReady,type ElectricalGroup,type ElectricalModelView} from './electricalModelView'
import {electricalModelScene} from './electricalModelScene'
import {LargeNetworkView} from './LargeNetworkView'
import './gridSource.css'

type Model={model_ref:string;name:string}
type Target={query:Record<string,unknown>;label:string;expected?:ThreadElectricalViewRequest}
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)
const label=(v:unknown)=>typeof v==='string'&&v.length>0&&v.length<=512
function models(value:unknown):Model[]{
  if(!record(value)||!Array.isArray(value.scopes)||value.scopes.length>1000)throw new Error('电网模型目录无效。')
  const seen=new Set<string>()
  return value.scopes.map(item=>{
    if(!record(item)||!label(item.model_ref)||!label(item.name)||seen.has(item.model_ref as string))throw new Error('电网模型身份无效。')
    seen.add(item.model_ref as string);return {model_ref:item.model_ref as string,name:item.name as string}
  })
}
function failure(cause:unknown):string {
  const body=record(cause)&&'body'in cause?cause.body:undefined
  if(body){const f=parseElectricalViewFailure(body);if(f)return `电气视图暂不可用：${f.code}。${f.recovery_action||''}`}
  return cause instanceof Error?cause.message:'电气视图暂时无法读取。'
}
function requestTarget(request:ThreadElectricalViewRequest,name=request.model_ref):Target {
  return {label:name,expected:request,query:{model_ref:request.model_ref,representation:request.representation,
    expected_model_revision:request.model_revision,selection_ref:request.selection_ref,
    ...(request.target?{parent_view_ref:request.view_ref,target:request.target}:{}),
    ...(request.artifact_ref?{artifact_ref:request.artifact_ref}:{})}}
}
function restoredTarget(key?:string,requestIdentity?:string):Target[] {
  if(!key)return []
  try{
    const saved:unknown=JSON.parse(sessionStorage.getItem(key)||'null')
    if(!record(saved))return []
    if(requestIdentity&&saved.appliedRequestIdentity!==requestIdentity)return []
    const request=parseThreadDisplayRequest(saved.request)
    return request?.schema==='capstone-electrical-view-request/1'?[requestTarget(request,label(saved.name)?saved.name as string:request.model_ref)]:[]
  }catch{return []}
}
export default function ElectricalModelWorkspace({transport,requestedView,requestNonce,onManualNavigate,storageKey}:{
  transport:HttpThreadTransport;requestedView?:ThreadElectricalViewRequest;requestNonce?:number;onManualNavigate?:()=>void;storageKey?:string
}) {
  const requestIdentity=JSON.stringify([requestedView,requestNonce])
  const [catalog,setCatalog]=useState<Model[]>([]),[path,setPath]=useState<Target[]>(()=>restoredTarget(storageKey,requestedView?requestIdentity:undefined)),[refresh,setRefresh]=useState(0)
  const appliedRequest=useRef(path.length?requestIdentity:null)
  const [manifest,setManifest]=useState<ElectricalViewReady>(),[view,setView]=useState<ElectricalModelView>()
  const [groups,setGroups]=useState<ElectricalGroup[]>([]),[cursor,setCursor]=useState<string|null>(null)
  const [query,setQuery]=useState(''),[error,setError]=useState(''),[progress,setProgress]=useState(''),[busy,setBusy]=useState(false)
  const [preparing,setPreparing]=useState<string>(),generation=useRef(0),controller=useRef<AbortController|null>(null)
  const loadedGroups=useRef<ElectricalGroup[]>([]),seenCursors=useRef(new Set<string>())
  const target=path.at(-1)
  useEffect(()=>{
    if(!requestedView||appliedRequest.current===requestIdentity)return
    appliedRequest.current=requestIdentity
    setPath([requestTarget(requestedView)])
  },[requestIdentity])
  useEffect(()=>{
    if(requestedView)return
    const stop=new AbortController()
    void transport.electricalModels(stop.signal).then(value=>{if(!stop.signal.aborted)setCatalog(models(value))})
      .catch(cause=>{if(!stop.signal.aborted)setError(failure(cause))})
    return()=>stop.abort()
  },[transport,!!requestedView])
  async function directory(ready:ElectricalViewReady,next:string|undefined,signal:AbortSignal,ticket:number){
    const page=parseElectricalViewPage(await transport.electricalRead({view_ref:ready.view_ref,stream:'groups',limit:200,...(next?{cursor:next}:{})},signal))
    if(signal.aborted||generation.current!==ticket)return
    for(const field of ['view_ref','model_ref','model_revision','selection_ref','source_snapshot_ref'] as const)
      if(page[field]!==ready[field])throw new Error('目录来源版本不一致，请重新打开。')
    if(page.stream!=='groups'||page.total_count!==ready.streams.groups.total_count||page.next_cursor===next)throw new Error('站点分页不一致。')
    const items=next?[...loadedGroups.current,...page.records as ElectricalGroup[]]:page.records as ElectricalGroup[]
    if(new Set(items.map(item=>item.id)).size!==items.length)throw new Error('站点目录包含重复记录。')
    if(items.length>page.total_count||(!page.next_cursor&&items.length!==page.total_count)
      ||(page.next_cursor&&(seenCursors.current.has(page.next_cursor)||!page.records.length||items.length>=page.total_count)))
      throw new Error('站点分页不完整或游标重复。')
    if(page.next_cursor)seenCursors.current.add(page.next_cursor)
    loadedGroups.current=items;setGroups(items);setCursor(page.next_cursor)
  }
  useEffect(()=>{
    const stop=new AbortController(),ticket=++generation.current;controller.current=stop
    loadedGroups.current=[];seenCursors.current.clear()
    setError('');setManifest(undefined);setView(undefined);setGroups([]);setCursor(null);setPreparing(undefined);setQuery('')
    if(!target)return()=>stop.abort()
    setBusy(true);setProgress('正在打开电气模型…')
    void (async()=>{
      const opened=parseElectricalViewOpen(await transport.electricalOpen(target.query,stop.signal))
      if(stop.signal.aborted||generation.current!==ticket)return
      if(opened.state==='preparing'){setPreparing(opened.preparation_ref);setProgress('网关正在准备模型结构。');return}
      if(target.expected)for(const field of ['view_ref','model_ref','model_revision','selection_ref','source_snapshot_ref','representation','target','artifact_ref'] as const)
        if((opened[field]??null)!==(target.expected[field]??null))throw new Error('来源版本已变化，请重新打开该模型。')
      setManifest(opened)
      if(storageKey){
        const request=parseThreadDisplayRequest({schema:'capstone-electrical-view-request/1',source_id:'data-gateway',
          ...Object.fromEntries(['model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref','representation','target','artifact_ref'].map(field=>[field,opened[field]??null]))})
        if(request)try{sessionStorage.setItem(storageKey,JSON.stringify({request,name:target.label,appliedRequestIdentity:requestIdentity}))}catch{/* Storage is optional. */}
      }
      if(!opened.target&&opened.representation==='source_node_breaker')await directory(opened,undefined,stop.signal,ticket)
      else {
        const result=await loadElectricalModelView(opened,(q,s)=>transport.electricalRead(q,s),{mode:'closure',signal:stop.signal,
          onProgress:(_stream,loaded,total)=>{if(!stop.signal.aborted)setProgress(`正在读取局部模型 · ${loaded} / ${total}`)}})
        if(!stop.signal.aborted&&generation.current===ticket)setView(result)
      }
    })().catch(cause=>{if(!stop.signal.aborted)setError(failure(cause))}).finally(()=>{if(!stop.signal.aborted){setBusy(false);setProgress('')}})
    return()=>stop.abort()
  },[transport,target,refresh])
  const scene=useMemo(()=>view?electricalModelScene(view):undefined,[view])
  function expand(group:ElectricalGroup){
    if(!manifest)return
    onManualNavigate?.();setPath(previous=>[...previous,{label:group.name||'站点',query:{model_ref:manifest.model_ref,representation:manifest.representation,
      parent_view_ref:manifest.view_ref,expected_model_revision:manifest.model_revision,selection_ref:manifest.selection_ref,target:group.expand_target}}])
  }
  async function more(){
    if(!manifest||!cursor||busy||!controller.current)return
    setBusy(true);setError('');const stop=controller.current,ticket=generation.current
    try{await directory(manifest,cursor,stop.signal,ticket)}catch(cause){if(!stop.signal.aborted)setError(failure(cause))}
    finally{if(!stop.signal.aborted)setBusy(false)}
  }
  async function checkPreparation(){
    if(!preparing||busy||!controller.current)return
    const stop=controller.current;setBusy(true)
    try{
      const result=await transport.electricalJob(preparing,stop.signal)
      if(stop.signal.aborted)return
      if(!record(result)||!['queued','running','succeeded','failed'].includes(String(result.state)))throw new Error('模型准备状态无效。')
      if(result.state==='succeeded')setRefresh(value=>value+1)
      else if(result.state==='failed')setError('模型准备失败，请查看网关缺口后重新打开。')
      else setProgress('网关仍在准备模型结构。')
    }catch(cause){if(!stop.signal.aborted)setError(failure(cause))}finally{if(!stop.signal.aborted)setBusy(false)}
  }
  return <section className="grid-source-workspace" aria-label="电气模型">
    {!requestedView&&<label>电网模型<select aria-label="电网模型" value={String(path[0]?.query.model_ref||'')} onChange={event=>{
      const model=catalog.find(item=>item.model_ref===event.target.value);onManualNavigate?.();setPath(model?[{label:model.name,query:{model_ref:model.model_ref,representation:'source_node_breaker'}}]:[])
    }}><option value="">请选择电网模型</option>{catalog.map(item=><option key={item.model_ref} value={item.model_ref}>{item.name}</option>)}</select></label>}
    <nav aria-label="电气模型层级">{path.map((item,index)=><button key={index} aria-current={index===path.length-1?'location':undefined} onClick={()=>{onManualNavigate?.();setPath(previous=>previous.slice(0,index+1))}}>{item.label}</button>)}</nav>
    {error&&<><p role="alert">{error}</p>{target&&<button disabled={busy} onClick={()=>setRefresh(value=>value+1)}>重新读取此视图</button>}</>}{progress&&<p role="status">{progress}</p>}
    {preparing&&<button disabled={busy} onClick={()=>void checkPreparation()}>检查准备进度</button>}
    {manifest&&<>
      <p className="grid-source-note">{manifest.representation==='source_node_breaker'?'源设备接线 · 开关状态以来源记录为准；缺失接线不补线。结构可读不代表潮流可算。':'计算模型拓扑 · 元件对应当前模型包；计算状态和结果以计算服务记录为准。'}</p>
      {!view&&<>
        <label>查找已加载站点<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="站点名称"/></label>
        <p>{groups.length} / {manifest.streams.groups.total_count} 个站点 · 仅显示已加载目录</p>
        <ul className="large-network-results">{groups.filter(group=>!query||String(group.name||'').includes(query)).map(group=><li key={group.id}>
          <button onClick={()=>expand(group)}>{group.name||'未命名站点'} · {group.member_count} 个设备</button></li>)}</ul>
        {cursor&&<button disabled={busy} onClick={()=>void more()}>加载更多站点</button>}
      </>}
      {scene&&view&&<><LargeNetworkView scene={scene} title={target?.label||'电气接线'} storageKey="capstone-electrical-model" viewKey={manifest.view_ref}/>
        <p>{view.records.devices.length} 个设备 · {view.records.ports.length} 个端口 · {view.records.connections.length} 条源连接</p>
        {!!view.records.groups.length&&<details><summary>关联站点</summary>{view.records.groups.map(group=><button key={group.id} onClick={()=>expand(group)}>{group.name||'站点'}</button>)}</details>}
        <details><summary>边界与数据缺口 · {view.records.boundaries.length} / {view.records.issues.length}</summary>
          {view.records.issues.slice(0,50).map(issue=><p key={issue.id}>{issue.code}</p>)}</details></>}
      <details><summary>来源与版本</summary><p>本次捕获内容固定；数据库跨表事务一致性未验证。</p>
        <dl><dt>模型</dt><dd>{manifest.model_ref}</dd><dt>模型版本</dt><dd>{manifest.model_revision}</dd><dt>读取时间</dt><dd>{JSON.stringify(manifest.capture)}</dd></dl></details>
    </>}
  </section>
}
