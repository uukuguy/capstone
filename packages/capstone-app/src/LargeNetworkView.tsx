import {useEffect,useId,useRef,useState} from 'react'
import type {NetworkScene,SceneCamera,SceneSearchResult,SceneSelection,SceneStats,SceneRelated,SceneBundle} from './networkScene'
import type {SceneFrame,SceneWorkerRequest} from './networkScene.worker'
import {createNetworkRenderer} from './networkWebGL'
import {readNetworkCamera,writeNetworkCamera} from './threadNetworkCamera'
import './largeNetworkView.css'
import NetworkLegend from './NetworkLegend'
import {networkSymbol} from './networkSymbols'
import type {ScenePresentation} from './networkScenePresentation'

const FULL:SceneCamera={x:0,y:0,width:1000,height:600}
export type LargeNetworkViewProps={scene:NetworkScene;title?:string;focusIds?:readonly string[];focusKey?:string;focusMarkersOnly?:boolean;taskLayerReady?:boolean;storageKey?:string;viewKey?:string;onSelect?:(item:SceneSelection)=>void;onActivate?:(item:SceneSelection)=>void;canActivate?:(item:SceneSelection)=>boolean;onReady?:(stats:SceneStats)=>void;onReturnCurrentTask?:()=>void;returnCurrentTaskLabel?:string;returnTaskRequest?:number}
export default function LargeNetworkView({scene,title='电网拓扑',focusIds=[],focusKey,focusMarkersOnly=false,taskLayerReady=true,storageKey,viewKey,onSelect,onActivate,canActivate,onReady,onReturnCurrentTask,returnCurrentTaskLabel='回到当前任务',returnTaskRequest}:LargeNetworkViewProps){
  const canvas=useRef<HTMLCanvasElement>(null),labels=useRef<HTMLDivElement>(null),worker=useRef<Worker|null>(null),renderer=useRef<ReturnType<typeof createNetworkRenderer>|null>(null)
  const camera=useRef<SceneCamera>(readNetworkCamera(storageKey,viewKey)||FULL),request=useRef(0),pendingView=useRef(false),dirtyView=useRef(false),ready=useRef(false),frame=useRef<SceneFrame|null>(null)
  const fullBounds=useRef<SceneCamera>(FULL)
  const pickedId=useRef<string|undefined>(undefined)
  const drawRequest=useRef(0),persistTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),drag=useRef<{x:number;y:number;camera:SceneCamera;moved:boolean}|null>(null)
  const activationRequest=useRef(0)
  const focusIdentity=focusKey??focusIds.join('\u0000'),lastAutoFocus=useRef<string|undefined>(undefined),consumedReturn=useRef<number|undefined>(undefined)
  const lastAutoView=useRef<string|undefined>(undefined),restoredInitialCamera=useRef(Boolean(readNetworkCamera(storageKey,viewKey)))
  const callbacks=useRef({onSelect,onActivate,canActivate,onReady,focusIds,focusMarkersOnly,taskLayerReady,returnTaskRequest,focusIdentity});callbacks.current={onSelect,onActivate,canActivate,onReady,focusIds,focusMarkersOnly,taskLayerReady,returnTaskRequest,focusIdentity}
  const [error,setError]=useState(''),[stats,setStats]=useState<SceneStats>(),[selected,setSelected]=useState<SceneSelection>(),[query,setQuery]=useState(''),[results,setResults]=useState<SceneSearchResult[]>([])
  const [bundleParallel,setBundleParallel]=useState(true),[expandedBundles,setExpandedBundles]=useState<string[]>([]),[neighborhood,setNeighborhood]=useState(true),[related,setRelated]=useState<SceneRelated>()
  const regional=scene.displayMode==='source-regional',presentation=useRef<ScenePresentation>({})
  presentation.current={bundleParallel,expandedBundles,neighborhood}
  const searchId=useRef(0),searchTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),controlId=useId()
  function send(message:SceneWorkerRequest){worker.current?.postMessage(message)}
  function aspectCamera(next:SceneCamera):SceneCamera{
    const node=canvas.current,aspect=node&&node.clientWidth>0&&node.clientHeight>0?node.clientWidth/node.clientHeight:5/3
    const width=Math.max(next.width,next.height*aspect),height=width/aspect
    return {x:next.x+(next.width-width)/2,y:next.y+(next.height-height)/2,width,height}
  }
  function requestView(){
    if(!ready.current)return
    if(pendingView.current){dirtyView.current=true;return}
    pendingView.current=true;dirtyView.current=false
    send({type:'view',request:++request.current,camera:camera.current,pixels:canvas.current?.clientWidth||800,height:canvas.current?.clientHeight||480,focusIds:pickedId.current?[...new Set([...callbacks.current.focusIds,pickedId.current])]:callbacks.current.focusIds,...presentation.current,selectionId:pickedId.current})
  }
  function positionLabels(){
    const root=labels.current,node=canvas.current;if(!root||!node||!frame.current)return
    const c=camera.current
    for(let i=0;i<root.children.length;i++){
      const label=frame.current.labels[i],element=root.children[i] as HTMLElement
      const x=(label.x-c.x)/c.width*node.clientWidth,y=(label.y-c.y)/c.height*node.clientHeight
      element.style.transform=`translate(${x+label.dx}px,${y+label.dy}px)`;element.hidden=x<0||y<0||x>node.clientWidth||y>node.clientHeight
    }
  }
  function scheduleDraw(){
    cancelAnimationFrame(drawRequest.current)
    drawRequest.current=requestAnimationFrame(()=>{renderer.current?.draw(camera.current);positionLabels();requestView()})
  }
  function move(next:SceneCamera){
    camera.current=aspectCamera(next);scheduleDraw()
    clearTimeout(persistTimer.current);persistTimer.current=setTimeout(()=>writeNetworkCamera(storageKey,viewKey,camera.current),200)
  }
  function zoom(factor:number,relativeX=.5,relativeY=.5){
    const before=camera.current,width=Math.min(1800,Math.max(1,before.width*factor)),height=before.height*width/before.width
    move({x:before.x+(before.width-width)*relativeX,y:before.y+(before.height-height)*relativeY,width,height})
  }
  function locate(id:string){send({type:'locate',request:++request.current,id})}
  function expandBundle(bundle:SceneBundle){setExpandedBundles(current=>current.includes(bundle.id)?current:[...current,bundle.id])}
  function overview(){pickedId.current=undefined;setSelected(undefined);setRelated(undefined);setExpandedBundles([]);setBundleParallel(true);requestView()}
  function focus(){send({type:'focus',request:++request.current,ids:callbacks.current.focusIds,markersOnly:callbacks.current.focusMarkersOnly})}
  function applyReturn(){
    const current=callbacks.current
    if(!ready.current||!current.taskLayerReady||current.returnTaskRequest===undefined||current.returnTaskRequest===consumedReturn.current)return false
    consumedReturn.current=current.returnTaskRequest;focus();return true
  }
  useEffect(()=>{
    let alive=true;setError('');setSelected(undefined);setResults([]);setStats(undefined);setRelated(undefined);setExpandedBundles([])
    camera.current=readNetworkCamera(storageKey,viewKey)||FULL;ready.current=false;pendingView.current=false;frame.current=null;pickedId.current=undefined
    try{
      if(!canvas.current)throw new Error('电网画布暂不可用')
      renderer.current=createNetworkRenderer(canvas.current)
      const instance=new Worker(new URL('./networkScene.worker.ts',import.meta.url),{type:'module'});worker.current=instance
      instance.onmessage=event=>{
        if(!alive)return
        const data=event.data
        if(data.type==='ready'){
          fullBounds.current=data.bounds||FULL
          if(!readNetworkCamera(storageKey,viewKey))camera.current=fullBounds.current
          ready.current=true;camera.current=aspectCamera(camera.current);setStats(data.stats);callbacks.current.onReady?.(data.stats);requestView()
          const returned=applyReturn()
          if(lastAutoFocus.current!==undefined&&lastAutoFocus.current!==callbacks.current.focusIdentity)restoredInitialCamera.current=false
          const newAttention=lastAutoFocus.current!==callbacks.current.focusIdentity||lastAutoView.current!==viewKey&&!restoredInitialCamera.current
          if(!returned&&newAttention&&callbacks.current.focusIds.length&&!readNetworkCamera(storageKey,viewKey))focus()
          lastAutoFocus.current=callbacks.current.focusIdentity
          lastAutoView.current=viewKey
        }else if(data.type==='frame'){
          pendingView.current=false;frame.current=data;renderer.current?.upload(data);renderer.current?.draw(camera.current)
          if(canvas.current){canvas.current.dataset.drawnNodes=String(data.drawnNodes);canvas.current.dataset.drawnEdges=String(data.drawnEdges)}
          if(labels.current){labels.current.replaceChildren(...data.labels.map((label:SceneFrame['labels'][number])=>{const span=document.createElement('span');span.textContent=label.label;return span}));positionLabels()}
          setStats(previous=>previous?{...previous,drawnNodes:data.drawnNodes,drawnEdges:data.drawnEdges,representedEdges:data.representedEdges,bundledGroups:data.bundledGroups,limited:data.limited}:previous)
          if(dirtyView.current)requestView()
        }else if(data.type==='selected'){
          pickedId.current=data.item?.id;setSelected(data.item);setRelated(data.related);if(data.item)callbacks.current.onSelect?.(data.item);requestView()
          if(data.item&&data.request===activationRequest.current){if(data.item.type==='bundle')expandBundle(data.item);else if(!callbacks.current.canActivate||callbacks.current.canActivate(data.item))callbacks.current.onActivate?.(data.item)}
        }else if(data.type==='located'&&data.item){
          pickedId.current=data.item.id;setSelected(data.item);setRelated(data.related);callbacks.current.onSelect?.(data.item);move({x:data.x-110,y:data.y-66,width:220,height:132})
        }else if(data.type==='focused'){
          move(data.camera)
        }else if(data.type==='search'&&data.request===searchId.current)setResults(data.results)
        else if(data.type==='error')setError(data.message)
      }
      instance.onerror=()=>{if(alive)setError('电网布局或索引未完成，请重新打开视图。')}
      instance.postMessage({type:'load',scene,aspect:canvas.current.clientWidth&&canvas.current.clientHeight?canvas.current.clientWidth/canvas.current.clientHeight:5/3} satisfies SceneWorkerRequest)
    }catch(cause){setError(cause instanceof Error?cause.message:'大图渲染暂不可用')}
    const observer=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(()=>{
      const node=canvas.current;if(!node?.clientWidth||!node.clientHeight)return
      const before=camera.current,height=before.width*node.clientHeight/node.clientWidth
      camera.current={...before,y:before.y+(before.height-height)/2,height};scheduleDraw()
    });if(canvas.current)observer?.observe(canvas.current)
    return()=>{alive=false;ready.current=false;worker.current?.terminate();worker.current=null;renderer.current?.dispose();renderer.current=null;observer?.disconnect();cancelAnimationFrame(drawRequest.current);clearTimeout(persistTimer.current);clearTimeout(searchTimer.current)}
  },[scene,storageKey,viewKey])
  useEffect(()=>{if(ready.current){if(!applyReturn()&&lastAutoFocus.current!==focusIdentity&&focusIds.length)focus();lastAutoFocus.current=focusIdentity;requestView()}},[focusIdentity,returnTaskRequest,taskLayerReady])
  useEffect(()=>{if(ready.current)requestView()},[bundleParallel,expandedBundles,neighborhood])
  return <section className="large-network-view" aria-label={title}>
    <div className="large-network-toolbar"><strong>{title}</strong><div aria-label="电网图操作">
      <button type="button" aria-label="放大" onClick={()=>zoom(.8)}>＋</button><button type="button" aria-label="缩小" onClick={()=>zoom(1.25)}>−</button>
      <button type="button" onClick={()=>move(fullBounds.current)}>适配全图</button>{focusIds.length>0&&<button type="button" onClick={focus}>定位任务对象</button>}
      {onReturnCurrentTask&&<button type="button" onClick={onReturnCurrentTask}>{returnCurrentTaskLabel}</button>}
    </div></div>
    {regional&&<div className="large-network-overview-controls" aria-label="站点总览显示">
      <label><input type="checkbox" checked={bundleParallel} onChange={event=>setBundleParallel(event.target.checked)}/>合并并行回路</label>
      <label><input type="checkbox" checked={neighborhood} onChange={event=>setNeighborhood(event.target.checked)}/>突出直接关联</label>
      {(selected||expandedBundles.length>0)&&<button type="button" onClick={overview}>恢复总览</button>}
    </div>}
    <label className="large-network-search" htmlFor={controlId}>查找对象<input id={controlId} type="search" value={query} placeholder="名称或稳定 ID" onChange={event=>{
      const value=event.target.value;setQuery(value);clearTimeout(searchTimer.current);setResults([]);searchId.current=++request.current
      if(value.trim())searchTimer.current=setTimeout(()=>send({type:'search',request:searchId.current,query:value}),120)
    }}/></label>
    {results.length>0&&<ul className="large-network-results" aria-label="对象搜索结果">{results.map(item=><li key={`${item.type}:${item.id}`}><button type="button" onClick={()=>{locate(item.id);setResults([])}}>{item.label} <small>{item.kind} · {item.id}</small></button></li>)}</ul>}
    <div className="large-network-stage">
      <canvas ref={canvas} tabIndex={0} role="img" aria-label="可缩放电网拓扑；使用加减键缩放，方向键平移，搜索查找对象" onKeyDown={event=>{
        if(event.key==='+'||event.key==='=')zoom(.8)
        else if(event.key==='-')zoom(1.25)
        else if(event.key.startsWith('Arrow')){const c=camera.current,step=c.width*.07;move({...c,x:c.x+(event.key==='ArrowRight'?step:event.key==='ArrowLeft'?-step:0),y:c.y+(event.key==='ArrowDown'?step:event.key==='ArrowUp'?-step:0)})}
        else return;event.preventDefault()
      }} onWheel={event=>{if(!event.shiftKey)return;event.preventDefault();const r=event.currentTarget.getBoundingClientRect();zoom(event.deltaY>0?1.13:.88,(event.clientX-r.left)/r.width,(event.clientY-r.top)/r.height)}}
      onPointerDown={event=>{if(event.button!==0)return;drag.current={x:event.clientX,y:event.clientY,camera:{...camera.current},moved:false};event.currentTarget.setPointerCapture?.(event.pointerId)}}
      onPointerMove={event=>{const d=drag.current;if(!d)return;const rect=event.currentTarget.getBoundingClientRect(),dx=event.clientX-d.x,dy=event.clientY-d.y;if(Math.abs(dx)+Math.abs(dy)>3)d.moved=true;move({...d.camera,x:d.camera.x-dx*d.camera.width/rect.width,y:d.camera.y-dy*d.camera.height/rect.height})}}
      onPointerUp={event=>{const d=drag.current;drag.current=null;if(!d||d.moved)return;const rect=event.currentTarget.getBoundingClientRect(),c=camera.current;send({type:'pick',request:++request.current,x:c.x+(event.clientX-rect.left)/rect.width*c.width,y:c.y+(event.clientY-rect.top)/rect.height*c.height,tolerance:c.width/rect.width*10,...presentation.current,selectionId:pickedId.current})}}
      onDoubleClick={event=>{const rect=event.currentTarget.getBoundingClientRect(),c=camera.current,id=++request.current;activationRequest.current=id;send({type:'pick',request:id,x:c.x+(event.clientX-rect.left)/rect.width*c.width,y:c.y+(event.clientY-rect.top)/rect.height*c.height,tolerance:c.width/rect.width*10,...presentation.current,selectionId:pickedId.current})}}
      onPointerCancel={()=>{drag.current=null}}/>
      <div ref={labels} className="large-network-labels" aria-hidden="true"/>
      {!stats&&!error&&<p className="large-network-loading" role="status">正在准备布局与空间索引…</p>}
    </div>
    {error&&<p role="alert">{error}</p>}
    {stats&&<p className="large-network-counts" role="status">{stats.nodes.toLocaleString()} 个对象 · {stats.edges.toLocaleString()} 条连接{stats.limited?' · 当前缩放按细节预算显示，放大可查看更多对象':''}<span> · {scene.coordinateSystem==='geographic'?'来源地理坐标':'示意布局'} · Shift + 滚轮缩放</span></p>}
    {regional&&stats?.drawnEdges!==undefined&&<p className="large-network-counts">当前显示 {stats.drawnEdges} 条连线{stats.bundledGroups?`，其中 ${stats.bundledGroups} 束并行回路`:''}；源线路身份与数量保持不变。选择站点可查看直接关联。</p>}
    <NetworkLegend scene={scene}/>
    {selected&&<aside className="large-network-selection" aria-label="所选拓扑对象" aria-live="polite"><strong>{selected.label||selected.id}</strong><dl><dt>类型</dt><dd>{selected.type==='bundle'?'同端点源线路分组':networkSymbol(selected.kind).label}<small> · {selected.kind}</small></dd>{selected.type!=='bundle'&&<><dt>ID</dt><dd>{selected.id}</dd></>}{selected.sourceRef&&<><dt>来源</dt><dd>{selected.sourceRef}</dd></>}{selected.type==='node'&&selected.voltageKv!=null&&<><dt>电压等级</dt><dd>{selected.voltageKv} kV</dd></>}{selected.type!=='node'&&<><dt>端点</dt><dd>{selected.source} → {selected.target}</dd></>}{selected.details?.slice(0,20).map((detail,i)=><div key={i}><dt>{detail.label}</dt><dd>{detail.value}</dd></div>)}</dl>
      {selected.type==='bundle'?<><p>{selected.memberIds.length} 条独立源线路，仅合并显示，不做电气等值。</p><button type="button" onClick={()=>expandBundle(selected)}>展开{selected.memberIds.length}条源线路</button><ul className="large-network-members">{selected.members.map(member=><li key={member.id}><button type="button" aria-label={`查看回路：${member.id}`} onClick={()=>locate(member.id)}>{member.label}<small>{member.id} · {member.kind}</small></button></li>)}</ul>{selected.memberIds.length>selected.members.length&&<small>此处列出前 {selected.members.length} 条；可按完整源 ID 搜索其他成员。</small>}</>:onActivate&&(!canActivate||canActivate(selected))&&<button type="button" onClick={()=>onActivate(selected)}>展开所选对象</button>}
      {regional&&selected.type==='node'&&related&&<section className="large-network-related" aria-label="来源直接关联"><p>{`${related.totalNodes} 个直接关联对象 · ${Number.isSafeInteger(related.edges)?`${related.edges} 条源线路`:'源线路计数暂不可用'}`}</p>{related.nodes.map(item=><button type="button" key={item.id} onClick={()=>locate(item.id)}>{item.label}</button>)}{related.totalNodes>related.nodes.length&&<small>其余对象可通过名称或 ID 搜索。</small>}</section>}
    </aside>}
  </section>
}
export {LargeNetworkView}
