import { useEffect, useMemo, useRef, useState } from 'react'
import type { HttpThreadTransport } from './threadHttpTransport'
import { loadGridSourceView, type GridSourceLevel, type GridSourceObject, type GridSourceView } from './gridSource'
import { LargeNetworkView } from './LargeNetworkView'
import type { NetworkScene } from './networkScene'
import { useSessionViewState } from './workspaceSessionCache'
import './gridSource.css'

type Selection = { level: GridSourceLevel; selected_object_id?: string | null; label: string; sourceSnapshot?: string; sourceInstance?: string; sourceRule?: string }
const root: Selection = { level:'region', label:'华北' }
function restorePath(value: unknown): Selection[] {
  return Array.isArray(value)&&value.length>0&&value.length<=32&&value[0]?.level==='region'
    &&value.every(item=>item&&['region','station','equipment'].includes(item.level)
      &&typeof item.label==='string'&&item.label.length<=512
      &&(item.level==='region'||typeof item.selected_object_id==='string'&&item.selected_object_id.length<=512)
      &&['sourceSnapshot','sourceInstance','sourceRule'].every(key=>item[key]===undefined||typeof item[key]==='string'&&item[key].length<=512))
    ?value as Selection[]:[root]
}

export default function GridSourceWorkspace({ transport, onQuestion }: {
  transport: HttpThreadTransport; onQuestion: (view: GridSourceView, question: string) => Promise<void>
}) {
  const [savedPath,setSavedPath] = useSessionViewState<unknown>('source-topology.path',[root])
  const path=restorePath(savedPath)
  function setPath(next: Selection[] | ((previous: Selection[])=>Selection[])) {
    setSavedPath((previous:unknown)=>typeof next==='function'?next(restorePath(previous)):next)
  }
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
      scope_id:'north',level:selection.level,selected_object_id:selection.selected_object_id,
    },controller.signal,(nodes,edges)=>{if(generation.current===ticket)setCounts([nodes,edges])})
      .then(result=>{
        if(selection.sourceSnapshot && (result.page.source_snapshot.metadata_snapshot!==selection.sourceSnapshot
            || result.page.source_snapshot.source_instance!==selection.sourceInstance))
          throw new Error('来源快照已变化，请回到华北总览重新加载。')
        if(selection.sourceRule && result.page.selection.rule_sha256!==selection.sourceRule)
          throw new Error('来源选择规则已变化，请回到华北总览重新加载。')
        if(!controller.signal.aborted&&generation.current===ticket)setView(result)
      })
      .catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'源拓扑读取失败。')})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return()=>controller.abort()
  },[transport,selection,revision])
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
    if(object?.expand)setPath(previous=>[...previous,{...object.expand!,label:object.label||object.id,
      sourceSnapshot:typeof view?.page.source_snapshot.metadata_snapshot==='string'?view.page.source_snapshot.metadata_snapshot:undefined,
      sourceRule:typeof view?.page.selection.rule_sha256==='string'?view.page.selection.rule_sha256:undefined,
      sourceInstance:typeof view?.page.source_snapshot.source_instance==='string'?view.page.source_snapshot.source_instance:undefined}])
  }
  async function ask() {
    if(!view||!question.trim()||asking)return
    setAsking(true);setError('')
    try{await onQuestion(view,question.trim())}
    catch(cause){setError(cause instanceof Error?cause.message:'问题资料准备失败。')}
    finally{setAsking(false)}
  }
  return <section className="grid-source-workspace" aria-label="源电网拓扑">
    <header><strong>{selection.level==='region'?'华北 · 区域站点总览':selection.level==='station'?`${selection.label} · 站内元件`:`${selection.label} · 元件连接`}</strong><button type="button" disabled={loading} onClick={()=>setRevision(value=>value+1)}>重新加载</button></header>
    <nav aria-label="拓扑层级">{path.map((item,index)=><button key={`${index}:${item.selected_object_id||'north'}`} type="button"
      aria-current={index===path.length-1?'location':undefined} onClick={()=>setPath(previous=>previous.slice(0,index+1))}>{item.label}</button>)}</nav>
    <p className="grid-source-note">{selection.level==='region'?'站点总览用于导航；潮流与优化使用经校核的母线、线路、变压器等电气模型。':'按来源展示电气元件；开关状态、参数和连接完整性仍需校核。'} 双击对象可下钻；交叉线不表示电气相连。</p>
    {loading&&<p role="status">正在读取源拓扑 · {counts[0].toLocaleString()} 个节点 / {counts[1].toLocaleString()} 条连接</p>}
    {error&&<p role="alert">{error}</p>}
    {scene&&view&&<>
      <LargeNetworkView scene={scene} title={selection.label} storageKey="capstone-source-north" viewKey={`${selection.level}:${selection.selected_object_id||''}:${view.page.view_ref}:source-layout-v2`} onActivate={activate} canActivate={item=>!!objects.get(item.id)?.expand}/>
      <p>{view.nodes.length.toLocaleString()} 个源节点 · {view.edges.length.toLocaleString()} 条源连接 · 未定位端点 {view.unresolvedEndpoints.length}</p>
      <details><summary>来源与质量缺口</summary>
        <dl><dt>视图版本</dt><dd>{view.page.view_ref}</dd><dt>选择规则</dt><dd><pre>{JSON.stringify(view.page.selection,null,2)}</pre></dd>
          <dt>来源快照</dt><dd><pre>{JSON.stringify(view.page.source_snapshot,null,2)}</pre></dd></dl>
        <ul>{[...view.page.source_gaps,...view.page.gaps].map((gap,index)=><li key={index}>{typeof gap==='string'?gap:JSON.stringify(gap)}</li>)}</ul>
        {!!view.unresolvedEndpoints.length&&<p>部分连接的端点未包含在本视图中；这些连接保留来源身份，不推断电气连通性。</p>}
      </details>
      <label>基于此源视图提问<textarea value={question} onChange={event=>setQuestion(event.target.value)} rows={3}/></label>
      <button type="button" disabled={asking||!question.trim()} onClick={()=>void ask()}>{asking?'正在准备资料…':'在独立源拓扑会话中提问'}</button>
      <p className="grid-source-note">保存当前来源摘要并打开问题草稿，由你确认发送。现有会话的计算模型保持原选择。</p>
    </>}
  </section>
}
