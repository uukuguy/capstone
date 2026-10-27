import {useEffect,useMemo,useRef,useState} from 'react'
import type {HttpThreadTransport} from './threadHttpTransport'
import {parseThreadDisplayRequest,type ThreadElectricalViewRequest} from './threadViewRouting'
import {loadElectricalModelView,parseElectricalViewOpen,parseElectricalViewPage,parseElectricalViewFailure,
  type ElectricalViewReady,type ElectricalGroup,type ElectricalModelView} from './electricalModelView'
import {electricalModelScene} from './electricalModelScene'
import {LargeNetworkView} from './LargeNetworkView'
import type {SceneSelection,SceneSearchResult} from './networkScene'
import {createElectricalViewDownload,type ElectricalViewDownload,type ElectricalDownloadProgress} from './electricalViewDownload'
import './gridSource.css'

type Model={model_ref:string;name:string;publishedName:boolean;query:Record<string,unknown>}
type Target={query:Record<string,unknown>;label:string;expected?:ThreadElectricalViewRequest;mode?:'overview'|'closure'}
type LoadTiming={started:number;viewRef?:string;overviewMs?:number;detailMs?:number}
const record=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v)
const label=(v:unknown)=>typeof v==='string'&&v.length>0&&v.length<=512
const modelName=(v:unknown):v is string=>typeof v==='string'&&v.trim().length>0&&v.length<=2048&&!/[\u0000-\u001f\u007f]/.test(v)
function models(value:unknown):Model[]{
  if(!record(value)||!Array.isArray(value.scopes)||value.scopes.length>1000)throw new Error('电网模型目录无效。')
  const capability=record(value.electrical_views)?value.electrical_views:{},v2=record(capability.v2)?capability.v2:{}
  const version=record(v2.open_arguments)&&v2.open_arguments.view_schema==='gateway-electrical-view/2'?{view_schema:'gateway-electrical-view/2'}:{}
  const entries=new Map<string,Model>()
  for(const item of value.scopes){
    if(!record(item)||!label(item.model_ref)||!modelName(item.name)||entries.has(item.model_ref as string))throw new Error('电网模型身份无效。')
    const model_ref=item.model_ref as string
    entries.set(model_ref,{model_ref,name:item.name as string,publishedName:true,query:{model_ref,representation:'source_node_breaker',...version}})
  }
  const sources=capability.source_grid_models??[]
  if(!Array.isArray(sources)||sources.length>1000)throw new Error('电网模型目录无效。')
  const seen=new Set<string>()
  for(const item of sources){
    if(!record(item)||!label(item.model_ref)||seen.has(item.model_ref as string))throw new Error('电网模型身份无效。')
    const model_ref=item.model_ref as string;seen.add(model_ref)
    if(!record(item.open_arguments)||item.open_arguments.model_ref!==model_ref
      ||Object.keys(item.open_arguments).some(key=>!['model_ref','selection_profile'].includes(key))
      ||item.open_arguments.selection_profile!==undefined&&(typeof item.open_arguments.selection_profile!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(item.open_arguments.selection_profile)))throw new Error('电网模型打开参数无效。')
    entries.set(model_ref,{model_ref,name:modelName(item.name)?item.name:entries.get(model_ref)?.name??'未命名电网',
      publishedName:modelName(item.name)||entries.get(model_ref)?.publishedName===true,
      query:{...item.open_arguments,representation:'source_node_breaker',...version}})
  }
  return [...entries.values()]
}
function failure(cause:unknown):string {
  const body=record(cause)&&'body'in cause?cause.body:undefined
  if(body){const f=parseElectricalViewFailure(body);if(f)return `电气视图暂不可用：${f.code}。${f.recovery_action||''}`}
  return cause instanceof Error?cause.message:'电气视图暂时无法读取。'
}
function requestTarget(request:ThreadElectricalViewRequest,name=request.target?'局部电气接线':request.name||'电网模型',mode?:Target['mode']):Target {
  return {label:name,expected:request,query:{model_ref:request.model_ref,representation:request.representation,
    expected_model_revision:request.model_revision,selection_ref:request.selection_ref,
    ...(request.target?{...(request.parent_view_ref?{parent_view_ref:request.parent_view_ref}:{}),target:request.target}:{
      ...(request.view_schema?{view_schema:request.view_schema}:{}),
      ...(request.selection_profile?{selection_profile:request.selection_profile}:{}),
      ...(request.boundary_policy?{boundary_policy:request.boundary_policy}:{})}),
    ...(request.artifact_ref?{artifact_ref:request.artifact_ref}:{})},mode}
}
function restoredTarget(key?:string,requestIdentity?:string):Target[] {
  if(!key)return []
  try{
    const saved:unknown=JSON.parse(sessionStorage.getItem(key)||'null')
    if(!record(saved))return []
    if(requestIdentity&&saved.appliedRequestIdentity!==requestIdentity)return []
    const rows=saved.format===2?saved.path:[{request:saved.request,label:saved.name}]
    if(!Array.isArray(rows)||rows.length>32)return []
    return rows.map(row=>{
      if(!record(row))throw Error('invalid saved path')
      const request=parseThreadDisplayRequest(row.request)
      if(request?.schema!=='capstone-electrical-view-request/1')throw Error('invalid saved descriptor')
      return requestTarget(request,modelName(row.label)&&row.label!==request.model_ref?row.label:request.target?'局部电气接线':request.name||'电网模型',
        row.mode==='overview'||row.mode==='closure'?row.mode:undefined)
    })
  }catch{return []}
}
function descriptor(ready:ElectricalViewReady,query:Target['query']):ThreadElectricalViewRequest|undefined {
  const coverage=record(ready.overview_coverage)?ready.overview_coverage:{},selection=record(coverage.source_selection)?coverage.source_selection:{}
  const parsed=parseThreadDisplayRequest({schema:'capstone-electrical-view-request/1',source_id:'data-gateway',
    ...(modelName(ready.name)?{name:ready.name}:{}),
    ...Object.fromEntries(['model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref','representation','target','artifact_ref'].map(field=>[field,ready[field]??null])),
    ...(ready.schema==='gateway-electrical-view/2'||query.view_schema?{view_schema:ready.schema}:{}),
    ...(ready.target?query.parent_view_ref?{parent_view_ref:query.parent_view_ref}:{}:{
      ...(selection.profile??query.selection_profile?{selection_profile:selection.profile??query.selection_profile}:{}),
      ...(selection.boundary_policy??query.boundary_policy?{boundary_policy:selection.boundary_policy??query.boundary_policy}:{})})})
  return parsed?.schema==='capstone-electrical-view-request/1'?parsed:undefined
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
  const [background,setBackground]=useState<ElectricalDownloadProgress>(),[userPaused,setUserPaused]=useState(false)
  const backgroundRef=useRef<{download:ElectricalViewDownload;viewRef:string;transport:HttpThreadTransport}|undefined>(undefined)
  const backgroundGeneration=useRef(0),paused=useRef(false),resolved=useRef(new Map<Target,ThreadElectricalViewRequest>())
  const resolvedNames=useRef(new Map<Target,string>())
  const knownModelNames=useRef(new Map<string,string>())
  const backgroundState=useRef<ElectricalDownloadProgress['state']|undefined>(undefined)
  const timingRef=useRef<LoadTiming|undefined>(undefined),timingFrame=useRef<number|undefined>(undefined)
  const [timing,setTiming]=useState<LoadTiming>()
  function resetTiming(){if(timingFrame.current!==undefined)cancelAnimationFrame(timingFrame.current);timingFrame.current=undefined;timingRef.current=undefined;setTiming(undefined)}
  function clearBackground(){backgroundGeneration.current++;backgroundRef.current?.download.dispose();backgroundRef.current=undefined;backgroundState.current=undefined;setBackground(undefined);paused.current=false;setUserPaused(false)}
  useEffect(()=>()=>{backgroundGeneration.current++;backgroundRef.current?.download.dispose();if(timingFrame.current!==undefined)cancelAnimationFrame(timingFrame.current)},[])
  const loadedGroups=useRef<ElectricalGroup[]>([]),seenCursors=useRef(new Set<string>())
  const target=path.at(-1)
  useEffect(()=>{
    if(!requestedView||appliedRequest.current===requestIdentity)return
    appliedRequest.current=requestIdentity
    clearBackground();resetTiming()
    setPath([requestTarget(requestedView)])
  },[requestIdentity])
  useEffect(()=>{
    if(requestedView)return
    const stop=new AbortController()
    void transport.electricalModels(stop.signal).then(value=>{if(!stop.signal.aborted){
      const available=models(value)
      for(const model of available)if(model.publishedName)knownModelNames.current.set(model.model_ref,model.name)
      setCatalog(available.map(model=>({...model,name:knownModelNames.current.get(model.model_ref)??model.name})))
    }})
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
    if(backgroundRef.current?.transport!==transport&&backgroundRef.current){clearBackground();resetTiming()}
    if(backgroundState.current!=='error'&&backgroundState.current!=='complete')backgroundRef.current?.download.pause()
    loadedGroups.current=[];seenCursors.current.clear()
    setError('');setManifest(undefined);setView(undefined);setGroups([]);setCursor(null);setPreparing(undefined);setQuery('')
    if(!target)return()=>stop.abort()
    setBusy(true);setProgress('正在打开电气模型…')
    void (async()=>{
      if(target.expected?.target&&!target.expected.parent_view_ref)throw new Error('保存的局部视图缺少父视图，请从模型目录重新打开。')
      if(path.length===1&&!timingRef.current){timingRef.current={started:performance.now()};setTiming({...timingRef.current})}
      const opened=parseElectricalViewOpen(await transport.electricalOpen(target.query,stop.signal))
      if(stop.signal.aborted||generation.current!==ticket)return
      if(opened.state==='preparing'){setPreparing(opened.preparation_ref);setProgress('网关正在准备模型结构。');return}
      if(target.expected?.view_schema&&target.expected.view_schema!==opened.schema)throw new Error('来源版本已变化，请重新打开该模型。')
      if(target.expected)for(const field of ['view_ref','model_ref','model_revision','selection_ref','source_snapshot_ref','representation','target','artifact_ref'] as const)
        if((opened[field]??null)!==(target.expected[field]??null))throw new Error('来源版本已变化，请重新打开该模型。')
      for(const [key,field] of [['model_ref','model_ref'],['expected_model_revision','model_revision'],['selection_ref','selection_ref'],['target','target'],['view_schema','schema']] as const)
        if(target.query[key]!==undefined&&target.query[key]!==opened[field])throw new Error('来源版本已变化，请重新打开该模型。')
      setManifest(opened)
      if(modelName(opened.name)){
        const name=opened.name;knownModelNames.current.set(opened.model_ref,name)
        setCatalog(previous=>previous.map(model=>model.model_ref===opened.model_ref?{...model,name,publishedName:true}:model))
      }
      if(path.length===1&&!opened.target&&modelName(opened.name))resolvedNames.current.set(target,opened.name)
      if(path.length===1&&timingRef.current&&!opened.target){timingRef.current.viewRef=opened.view_ref;setTiming({...timingRef.current})}
      const saved=descriptor(opened,target.query)
      if(saved)resolved.current.set(target,saved)
      if(storageKey){
        const savedPath=path.map(item=>({label:resolvedNames.current.get(item)??item.label,mode:item.mode,request:resolved.current.get(item)??item.expected}))
        if(savedPath.every(item=>item.request))try{sessionStorage.setItem(storageKey,JSON.stringify({format:2,path:savedPath,appliedRequestIdentity:requestIdentity}))}catch{/* Storage is optional. */}
      }
      const overview=opened.schema==='gateway-electrical-view/2'&&opened.representation==='source_node_breaker'
        &&(target.mode==='overview'||!opened.target||opened.default_stream==='summary_nodes'||opened.default_stream==='summary_edges')&&target.mode!=='closure'
      if(!overview&&!opened.target&&opened.representation==='source_node_breaker')await directory(opened,undefined,stop.signal,ticket)
      else {
        const result=await loadElectricalModelView(opened,(q,s)=>transport.electricalRead(q,s),{mode:overview?'overview':'closure',signal:stop.signal,
          onProgress:(_stream,loaded,total)=>{if(!stop.signal.aborted)setProgress(`正在读取${overview?'完整概览':'局部模型'} · ${loaded} / ${total}`)}})
        if(!stop.signal.aborted&&generation.current===ticket){
          setView(result)
          if(overview&&path.length===1&&!opened.target){
            if(backgroundRef.current?.viewRef!==opened.view_ref){
              clearBackground();const current=backgroundGeneration.current
              const measurement=timingRef.current
              const download=createElectricalViewDownload(opened,(q,s)=>transport.electricalRead(q,s),value=>{
                if(backgroundGeneration.current===current){
                  backgroundState.current=value.state;setBackground(value)
                  if(value.state==='complete'&&measurement&&timingRef.current===measurement&&measurement.detailMs===undefined){
                    measurement.detailMs=Math.max(0,performance.now()-measurement.started);setTiming({...measurement})
                  }
                }
              })
              backgroundRef.current={download,viewRef:opened.view_ref,transport}
            }
          }
        }
      }
    })().catch(cause=>{if(!stop.signal.aborted)setError(failure(cause))}).finally(()=>{
      if(!stop.signal.aborted&&generation.current===ticket){setBusy(false);setProgress('');if(!paused.current&&backgroundState.current!=='error'&&backgroundState.current!=='complete')backgroundRef.current?.download.start()}
    })
    return()=>stop.abort()
  },[transport,target,refresh])
  const scene=useMemo(()=>view?electricalModelScene(view):undefined,[view])
  function overviewFirstFrame(){
    const measurement=timingRef.current
    if(!measurement||measurement.overviewMs!==undefined||manifest?.view_ref!==measurement.viewRef||!view?.loadedStreams.includes('summary_nodes'))return
    if(timingFrame.current!==undefined)cancelAnimationFrame(timingFrame.current)
    timingFrame.current=requestAnimationFrame(()=>{
      timingFrame.current=undefined
      if(timingRef.current!==measurement||measurement.overviewMs!==undefined)return
      measurement.overviewMs=Math.max(0,performance.now()-measurement.started);setTiming({...measurement})
    })
  }
  function expandTarget(expand_target:string,name:string,mode:Target['mode']='closure'){
    if(!manifest||busy)return
    onManualNavigate?.();setPath(previous=>[...previous,{label:name,mode,query:{model_ref:manifest.model_ref,representation:manifest.representation,
      parent_view_ref:manifest.view_ref,expected_model_revision:manifest.model_revision,selection_ref:manifest.selection_ref,target:expand_target}}])
  }
  function activation(item:SceneSelection|SceneSearchResult){
    if(!view||item.type==='bundle')return
    const node=view.records.summary_nodes.find(node=>node.id===item.id)
    if(node?.expand_target)return {target:node.expand_target,
      label:node.group_kind==='station'?`${node.name||node.id} · 电气接线`:node.name||node.id,
      actionLabel:node.group_kind==='grid'?'进入区域概览':node.group_kind==='station'?'进入电气接线':'查看局部接线',
      mode:node.group_kind==='grid'?'overview' as const:'closure' as const}
    const edge=view.records.summary_edges.find(edge=>edge.id===item.id)
    if(edge?.expand_target)return {target:edge.expand_target,label:`${edge.member_count} 条源线路 · 线路接线`,actionLabel:'查看线路接线',mode:'closure' as const}
  }
  function expand(group:ElectricalGroup){
    expandTarget(group.expand_target,group.name||'站点')
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
      const model=catalog.find(item=>item.model_ref===event.target.value);onManualNavigate?.();clearBackground();resetTiming();setPath(model?[{label:model.name,query:model.query}]:[])
    }}><option value="">请选择电网模型</option>{catalog.map(item=><option key={item.model_ref} value={item.model_ref}>{item.name}</option>)}</select></label>}
    <nav aria-label="电气模型层级">{path.map((item,index)=><button key={index} aria-current={index===path.length-1?'location':undefined} onClick={()=>{
      onManualNavigate?.();setPath(previous=>previous.slice(0,index+1).map(entry=>{const saved=resolved.current.get(entry)??entry.expected;return saved?requestTarget(saved,resolvedNames.current.get(entry)??entry.label,entry.mode):entry}))
    }}>{resolvedNames.current.get(item)??item.label}</button>)}</nav>
    {error&&<><p role="alert">{error}</p>{target&&<button disabled={busy} onClick={()=>setRefresh(value=>value+1)}>重新读取此视图</button>}</>}{progress&&<p role="status">{progress}</p>}
    {preparing&&<button disabled={busy} onClick={()=>void checkPreparation()}>检查准备进度</button>}
    {timing&&manifest?.schema==='gateway-electrical-view/2'&&manifest.representation==='source_node_breaker'&&<details aria-label="电气视图加载耗时" data-model-open-start-ms={timing.started}
      data-overview-ready-ms={timing.overviewMs} data-detail-complete-ms={timing.detailMs}>
      <summary>加载耗时</summary>
      <p>概览可交互：{timing.overviewMs===undefined?'尚未就绪':`${(timing.overviewMs/1000).toFixed(2)} 秒`}</p>
      <p>全部明细下载：{timing.detailMs===undefined?'尚未完成':`${(timing.detailMs/1000).toFixed(2)} 秒`}</p>
      <small>均从开始打开模型计时，包含暂停与导航等待；缓存命中会影响耗时。</small>
    </details>}
    {!backgroundRef.current&&path.length>1&&path[0].expected?.view_schema==='gateway-electrical-view/2'&&
      <p role="status">后台明细尚未恢复；返回根概览后继续下载。</p>}
    {backgroundRef.current&&<aside aria-label="后台明细下载" className="large-network-toolbar">
      <details><summary>后台明细 {background?.loaded??0} / {background?.total??0}{background?.state==='complete'?' · 已完成':background?.state==='error'?' · 下载失败':background?.state==='paused'?' · 已暂停':''}</summary>
        {background?.error&&<p role="status">后台缓存：{background.error}。概览仍可使用。</p>}
        {background&&Object.entries(background.streams).map(([stream,value])=><p key={stream}>{stream} · {value.loaded} / {value.total}</p>)}
      </details>
      {background?.state!=='complete'&&<button disabled={busy} onClick={()=>{
        if(userPaused||background?.state==='error'){paused.current=false;setUserPaused(false);backgroundRef.current?.download.start()}
        else {paused.current=true;setUserPaused(true);backgroundRef.current?.download.pause()}
      }}>{userPaused||background?.state==='error'?'继续后台下载':'暂停后台下载'}</button>}
    </aside>}
    {manifest&&<>
      <p className="grid-source-note">{view?.loadedStreams.includes('summary_nodes')?<><span>单击厂站后选择“进入电气接线”，也可双击厂站。缩放仅调整视野。</span> 来源概览非电气等值。</>:
        manifest.representation==='source_node_breaker'?'源设备接线 · 开关状态以来源记录为准；缺失接线不补线。结构可读不代表潮流可算。':'计算模型拓扑 · 元件对应当前模型包；计算状态和结果以计算服务记录为准。'}</p>
      {record(manifest.derivation)&&manifest.derivation.demo_only===true&&<p className="grid-source-note">演示补全模型 · 不代表电网真实运行工况。</p>}
      {!view&&manifest.schema==='gateway-electrical-view/1'&&manifest.representation==='source_node_breaker'&&!manifest.target&&<>
        <label>查找已加载站点<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="站点名称"/></label>
        <p>{groups.length} / {manifest.streams.groups.total_count} 个站点 · 仅显示已加载目录</p>
        <ul className="large-network-results">{groups.filter(group=>!query||String(group.name||'').includes(query)).map(group=><li key={group.id}>
          <button onClick={()=>expand(group)}>{group.name||'未命名站点'} · {group.member_count} 个设备</button></li>)}</ul>
        {cursor&&<button disabled={busy} onClick={()=>void more()}>加载更多站点</button>}
      </>}
      {scene&&view&&<>
        <LargeNetworkView scene={scene} title={view.loadedStreams.includes('summary_nodes')?`${target?resolvedNames.current.get(target)??target.label:'电网'} · 厂站概览`:target?.label||'电气接线'} storageKey="capstone-electrical-model" viewKey={manifest.view_ref}
        onFirstFrame={overviewFirstFrame}
        activationLabel={item=>!busy?activation(item)?.actionLabel:undefined}
        canActivate={item=>!busy&&!!activation(item)} onActivate={item=>{const next=activation(item);if(next)expandTarget(next.target,next.label,next.mode)}}/>
        {view.loadedStreams.includes('summary_nodes')?<p>{view.records.summary_nodes.length} 个概览分组 · {view.records.summary_edges.length} 条来源线路分组 · 当前层概览完整</p>:<p>{view.records.devices.length} 个设备 · {view.records.ports.length} 个端口 · {view.records.connections.length} 条源连接</p>}
        {!!view.records.groups.length&&<details><summary>关联站点</summary>{view.records.groups.map(group=><button key={group.id} onClick={()=>expand(group)}>{group.name||'站点'}</button>)}</details>}
        <details><summary>边界与数据缺口 · {view.records.boundaries.length} / {view.records.issues.length}</summary>
          {view.records.issues.slice(0,50).map(issue=><p key={issue.id}>{issue.code}</p>)}</details></>}
      <details><summary>来源与版本</summary><p>本次捕获内容固定；数据库跨表事务一致性未验证。</p>
        <dl><dt>模型</dt><dd>{manifest.model_ref}</dd><dt>模型版本</dt><dd>{manifest.model_revision}</dd><dt>读取时间</dt><dd>{JSON.stringify(manifest.capture)}</dd></dl></details>
    </>}
  </section>
}
