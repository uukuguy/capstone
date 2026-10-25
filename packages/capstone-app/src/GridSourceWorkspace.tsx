import { useEffect, useMemo, useRef, useState } from 'react'
import type { HttpThreadTransport } from './threadHttpTransport'
import { loadGridSourceView, type GridSourceLevel, type GridSourceObject, type GridSourceView } from './gridSource'
import { LargeNetworkView } from './LargeNetworkView'
import type { NetworkScene } from './networkScene'
import { useSessionViewState } from './workspaceSessionCache'
import type { ThreadSourceViewRequest } from './threadViewRouting'
import './gridSource.css'

type Selection = { level: GridSourceLevel; selected_object_id?: string | null; label: string; sourceSnapshot?: string; sourceInstance?: string; sourceRule?: string; viewRef?:string; voltageMin?:number|null }
const root: Selection = { level:null, label:'华北全网元件' }
const region: Selection = { level:'region', label:'华北站点总览' }
function restorePath(value: unknown,fallback:Selection=root): Selection[] {
  return Array.isArray(value)&&value.length>0&&value.length<=32&&(value[0]?.level===null||value[0]?.level==='region')
    &&value.every(item=>item&&(item.level===null||['region','station','equipment'].includes(item.level))
      &&typeof item.label==='string'&&item.label.length<=512
      &&(item.level===null||item.level==='region'||typeof item.selected_object_id==='string'&&item.selected_object_id.length<=512)
      &&['sourceSnapshot','sourceInstance','sourceRule','viewRef'].every(key=>item[key]===undefined||typeof item[key]==='string'&&item[key].length<=512)
      &&(item.voltageMin==null||typeof item.voltageMin==='number'&&Number.isFinite(item.voltageMin)&&item.voltageMin>=0))
    ?value as Selection[]:[fallback]
}

export default function GridSourceWorkspace({ transport, onQuestion, requestedView, requestNonce, onManualNavigate }: {
  transport: HttpThreadTransport; onQuestion: (view: GridSourceView, question: string) => Promise<void>
  requestedView?:ThreadSourceViewRequest;requestNonce?:number;onManualNavigate?:()=>void
}) {
  const scopeId=requestedView?.scope_id||'north',scopeName=requestedView?.scope_name||'华北'
  const scopedRoot=useMemo<Selection>(()=>({...root,label:`${scopeName}全网元件`,voltageMin:requestedView?.voltage_min_kv}),[scopeName,requestedView?.voltage_min_kv])
  const scopedRegion=useMemo<Selection>(()=>({...region,label:`${scopeName}站点总览`,voltageMin:requestedView?.voltage_min_kv}),[scopeName,requestedView?.voltage_min_kv])
  const [savedPath,setSavedPath] = useSessionViewState<unknown>(`source-topology.path:${scopeId}`,[scopedRoot])
  const path=restorePath(savedPath,scopedRoot)
  function setPath(next: Selection[] | ((previous: Selection[])=>Selection[])) {
    setSavedPath((previous:unknown)=>typeof next==='function'?next(restorePath(previous,scopedRoot)):next)
  }
  useEffect(()=>{
    if(!requestedView)return
    const target:Selection={level:requestedView.level,selected_object_id:requestedView.selected_object_id,
      label:requestedView.selected_object_id||`${scopeName}${requestedView.level==='region'?'站点总览':'全网元件'}`,viewRef:requestedView.view_ref,
      voltageMin:requestedView.voltage_min_kv,sourceSnapshot:requestedView.source_snapshot.metadata_snapshot,
      sourceInstance:requestedView.source_snapshot.source_instance}
    setPath(target.level===null?[target]:[scopedRoot,target])
  },[requestedView?.view_ref,requestedView?.scope_id,requestedView?.scope_name,requestedView?.level,requestedView?.selected_object_id,
    requestedView?.voltage_min_kv,requestedView?.source_snapshot.metadata_snapshot,requestedView?.source_snapshot.source_instance,requestNonce])
  const [view,setView] = useState<GridSourceView>()
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(false)
  const [counts,setCounts] = useState([0,0])
  const [revision,setRevision] = useState(0)
  const [question,setQuestion] = useState('当前源拓扑视图有多少节点和连接，各是什么对象类型？请说明选择规则、边界策略、来源快照及质量缺口。')
  const [asking,setAsking] = useState(false)
  const generation = useRef(0)
  const selection = path[path.length-1]
  useEffect(()=>{
    const controller=new AbortController(), ticket=++generation.current
    setView(undefined);setError('');setLoading(true);setCounts([0,0])
    void loadGridSourceView((query,signal)=>transport.gridSourceTopology(query,signal),{
      scope_id:scopeId,level:selection.level,selected_object_id:selection.selected_object_id,
      ...(selection.viewRef?{expected_view_ref:selection.viewRef}:{}),...(selection.voltageMin===undefined?{}:{voltage_min_kv:selection.voltageMin}),
    },controller.signal,(nodes,edges)=>{if(generation.current===ticket)setCounts([nodes,edges])})
      .then(result=>{
        if(selection.sourceSnapshot && (result.page.source_snapshot.metadata_snapshot!==selection.sourceSnapshot
            || result.page.source_snapshot.source_instance!==selection.sourceInstance))
          throw new Error(`来源快照已变化，请回到${scopeName}总览重新加载。`)
        if(selection.sourceRule && result.page.selection.rule_sha256!==selection.sourceRule)
          throw new Error(`来源选择规则已变化，请回到${scopeName}总览重新加载。`)
        if(!controller.signal.aborted&&generation.current===ticket)setView(result)
      })
      .catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'源拓扑读取失败。')})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return()=>controller.abort()
  },[transport,selection,revision,scopeId])
  const objects = useMemo(()=>new Map([...(view?.nodes||[]),...(view?.edges||[])].map(item=>[item.id,item])),[view])
  const nodeIds = useMemo(()=>new Set(view?.nodes.map(item=>item.id)),[view])
  const scene = useMemo<NetworkScene|undefined>(()=>view?{
    ref:view.page.view_ref,coordinateSystem:'schematic',displayMode:view.page.level==='region'?'source-regional':'source-detail',
    nodes:view.nodes.map(item=>({id:item.id,label:item.label||item.id,kind:item.kind,sourceRef:item.source_id,
      voltageKv:item.voltage_kv??item.vn_kv,boundary:item.boundary,
      details:[{label:'来源对象',value:item.source_id||item.id},{label:'边界对象',value:item.boundary?'是':'否'},
        ...(item.parent_id?[{label:'上级对象',value:item.parent_id}]:[]),...(item.station_id?[{label:'所属站点',value:item.station_id}]:[])]})),
    edges:view.edges.filter(item=>nodeIds.has(item.source!)&&nodeIds.has(item.target!)).map(item=>({id:item.id,source:item.source!,target:item.target!,kind:item.kind,
      label:item.label||item.id,sourceRef:item.source_id})),
  }:undefined,[view,nodeIds])
  function activate(item: {id:string}) {
    const object: GridSourceObject|undefined=objects.get(item.id)
    if(object?.expand){onManualNavigate?.();setPath(previous=>[...previous,{...object.expand!,label:object.label||object.id,
      sourceSnapshot:typeof view?.page.source_snapshot.metadata_snapshot==='string'?view.page.source_snapshot.metadata_snapshot:undefined,
      sourceRule:typeof view?.page.selection.rule_sha256==='string'?view.page.selection.rule_sha256:undefined,
      sourceInstance:typeof view?.page.source_snapshot.source_instance==='string'?view.page.source_snapshot.source_instance:undefined,
      voltageMin:typeof view?.page.selection.min_ac_kv==='number'?view.page.selection.min_ac_kv:selection.voltageMin}])}
  }
  async function ask() {
    if(!view||!question.trim()||asking)return
    setAsking(true);setError('')
    try{await onQuestion(view,question.trim())}
    catch(cause){setError(cause instanceof Error?cause.message:'问题资料准备失败。')}
    finally{setAsking(false)}
  }
  return <section className="grid-source-workspace" aria-label="源电网拓扑">
    <header><strong>{selection.level===null?`${scopeName} · 全网源元件`:selection.level==='region'?`${scopeName} · 区域站点总览`:selection.level==='station'?`${selection.label} · 站内元件`:`${selection.label} · 元件连接`}</strong><button type="button" disabled={loading} onClick={()=>{onManualNavigate?.();setPath(previous=>previous.map(item=>({...item,viewRef:undefined,sourceSnapshot:undefined,sourceInstance:undefined,sourceRule:undefined})));setRevision(value=>value+1)}}>重新加载</button></header>
    <nav aria-label={`${scopeName}拓扑视图`}><button type="button" aria-pressed={path[0].level===null} onClick={()=>{onManualNavigate?.();setPath([scopedRoot])}}>全网元件</button><button type="button" aria-pressed={path[0].level==='region'} onClick={()=>{onManualNavigate?.();setPath([scopedRegion])}}>站点总览</button></nav>
    <nav aria-label="拓扑层级">{path.map((item,index)=><button key={`${index}:${item.selected_object_id||scopeId}`} type="button"
      aria-current={index===path.length-1?'location':undefined} onClick={()=>{onManualNavigate?.();setPath(previous=>previous.slice(0,index+1))}}>{item.label}</button>)}</nav>
    <p className="grid-source-note">{selection.level==='region'?'站点总览用于导航；潮流与优化使用经校核的母线、线路、变压器等电气模型。':'按来源展示母线、变压器、开关等元件及连接；未做电气母线归并，状态和参数缺口保留。'} 双击对象可下钻；交叉线不表示电气相连。</p>
    {loading&&<p role="status">{`正在读取源拓扑 · ${counts[0].toLocaleString()} 个节点 / ${counts[1].toLocaleString()} 条连接`}</p>}
    {error&&<p role="alert">{error}</p>}
    {scene&&view&&<>
      <p className="grid-source-note">视图口径：{typeof view.page.selection.min_ac_kv==='number'?`交流电压下限 ${view.page.selection.min_ac_kv} kV`:'以来源筛选规则为准'}；目录范围和运行状态不作额外推断。</p>
      <LargeNetworkView scene={scene} title={selection.label} storageKey={`capstone-source-${scopeId}`} viewKey={`${selection.level}:${selection.selected_object_id||''}:${view.page.view_ref}:source-layout-v2`} onActivate={activate} canActivate={item=>!!objects.get(item.id)?.expand}/>
      <p>{view.nodes.length.toLocaleString()} 个源节点 · {view.edges.length.toLocaleString()} 条源连接 · 未定位端点 {view.unresolvedEndpoints.length}</p>
      <details><summary>来源与质量缺口</summary>
        <dl><dt>视图版本</dt><dd>{view.page.view_ref}</dd><dt>选择规则</dt><dd><pre>{JSON.stringify(view.page.selection,null,2)}</pre></dd>
          <dt>来源快照</dt><dd><pre>{JSON.stringify(view.page.source_snapshot,null,2)}</pre></dd></dl>
        <p>共 {view.page.source_gaps.length+view.page.gaps.length} 项源质量记录，当前显示前 50 项；完整记录保留在本视图的提问资料中。</p>
        <ul>{[...view.page.source_gaps,...view.page.gaps].slice(0,50).map((gap,index)=><li key={index}>{typeof gap==='string'?gap:JSON.stringify(gap)}</li>)}</ul>
        {!!view.unresolvedEndpoints.length&&<p>部分连接的端点未包含在本视图中；这些连接保留来源身份，不推断电气连通性。</p>}
      </details>
      <label>基于此源视图提问<textarea value={question} onChange={event=>setQuestion(event.target.value)} rows={3}/></label>
      <button type="button" disabled={asking||!question.trim()} onClick={()=>void ask()}>{asking?'正在准备资料…':'在独立源拓扑会话中提问'}</button>
      <p className="grid-source-note">保存当前来源摘要并打开问题草稿，由你确认发送。现有会话的计算模型保持原选择。</p>
    </>}
  </section>
}
