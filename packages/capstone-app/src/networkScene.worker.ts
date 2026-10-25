import {buildSceneIndex,focusScene,queryScene,searchScene,type SceneIndex} from './networkSceneIndex'
import type {NetworkScene,SceneCamera,SceneSelection,SceneRelated} from './networkScene'
import {networkSymbol,sceneGlyphs} from './networkSymbols'
import {pickPresentedScene,presentedBundle,sceneNeighborhood,type ScenePresentation} from './networkScenePresentation'

export type SceneWorkerRequest=
  |{type:'load';scene:NetworkScene;aspect?:number}
  |({type:'view';request:number;camera:SceneCamera;pixels:number;height?:number;focusIds:readonly string[]}&ScenePresentation)
  |({type:'pick';request:number;x:number;y:number;tolerance:number}&ScenePresentation)
  |{type:'search';request:number;query:string}
  |{type:'locate';request:number;id:string}
  |{type:'focus';request:number;ids:readonly string[];markersOnly?:boolean}
type Label={id:string;label:string;x:number;y:number;dx:number;dy:number}
export type SceneFrame={type:'frame';request:number;lines:Float32Array;points:Float32Array;labels:Label[];drawnNodes:number;drawnEdges:number;representedEdges:number;bundledGroups:number;limited:boolean}
const color=(selected:boolean,node=false,style?:{color?:readonly number[];state?:string})=>selected?[.12,.32,.63,1]:style?.state==='warning'?[.76,.39,.12,1]:style?.state==='disconnected'?[.65,.33,.25,1]:style?.color?[...style.color,1]:node?[.28,.43,.44,1]:[.48,.58,.60,.65]
function selection(index:SceneIndex,id:string):{item:SceneSelection;x:number;y:number}|undefined {
  const node=index.nodeIds.get(id)
  if(node!==undefined)return {item:{type:'node',...index.scene.nodes[node]},x:index.positions[node*2],y:index.positions[node*2+1]}
  const edge=index.edgeIds.get(id)
  if(edge===undefined)return
  const a=index.endpoints[edge*2]*2,b=index.endpoints[edge*2+1]*2
  return {item:{type:'edge',...index.scene.edges[edge]},x:(index.positions[a]+index.positions[b])/2,y:(index.positions[a+1]+index.positions[b+1])/2}
}
function related(index:SceneIndex,item:SceneSelection|undefined):SceneRelated|undefined{
  if(index.scene.displayMode!=='source-regional'||item?.type!=='node')return
  const near=sceneNeighborhood(index,item.id),ids=[...near.nodeIds].filter(id=>id!==item.id)
  return {nodes:ids.slice(0,20).map(id=>{const node=index.scene.nodes[index.nodeIds.get(id)!];return {id:node.id,label:node.label,kind:node.kind,type:'node'}}),totalNodes:ids.length,edges:near.edgeIds.size}
}
export function sceneFrame(index:SceneIndex,message:Extract<SceneWorkerRequest,{type:'view'}>):SceneFrame {
  const viewport=queryScene(index,message.camera),focused=new Set(message.focusIds)
  const nodes=new Set(viewport.nodeIndices),edges=new Set(viewport.edgeIndices)
  const priorities=message.selectionId?[message.selectionId,...message.focusIds.slice(0,63)]:message.focusIds.slice(0,64)
  for(const id of priorities){const n=index.nodeIds.get(id),e=index.edgeIds.get(id);if(n!==undefined)nodes.add(n);if(e!==undefined)edges.add(e)}
  const lineValues:number[]=[],pointValues:number[]=[],labels:Label[]=[]
  const scale=message.camera.width/Math.max(1,message.pixels)
  const detailed=index.scene.nodes.length<=1500||message.camera.width<index.bounds.width*.25
  const regional=index.scene.displayMode==='source-regional',near=regional&&message.neighborhood!==false&&message.selectionId&&index.nodeIds.has(message.selectionId)?sceneNeighborhood(index,message.selectionId):undefined
  const renderedBundles=new Set<string>();let drawnEdges=0,representedEdges=0
  for(const i of edges){
    let bundle=presentedBundle(index,i,message)
    if(bundle&&index.bundles.get(bundle)?.some(member=>focused.has(index.scene.edges[member].id)))bundle=undefined
    if(bundle){if(renderedBundles.has(bundle))continue;renderedBundles.add(bundle);representedEdges+=index.bundles.get(bundle)!.length}else representedEdges++
    drawnEdges++
    const edge=index.scene.edges[i],a=index.endpoints[i*2]*2,b=index.endpoints[i*2+1]*2,ax=index.positions[a],ay=index.positions[a+1],bx=index.positions[b],by=index.positions[b+1]
    const dx=bx-ax,dy=by-ay,length=Math.hypot(dx,dy)||1,offset=bundle?0:index.edgeOffsets[i]
    const chosen=focused.has(edge.id)||Boolean(bundle&&bundle===message.selectionId)
    const mx=(ax+bx)/2-dy/length*offset,my=(ay+by)/2+dx/length*offset,c=regional?(chosen?[.12,.32,.63,1]:near?near.edgeIds.has(edge.id)?[.18,.40,.65,.85]:[.5,.58,.63,.035]:[.45,.54,.59,.25]):color(chosen,false,edge)
    if(a===b){
      const radius=8+Math.abs(index.edgeOffsets[i])
      for(let segment=0;segment<16;segment++){const first=segment*Math.PI/8,next=(segment+1)*Math.PI/8;lineValues.push(ax+Math.cos(first)*radius,ay+Math.sin(first)*radius,...c,ax+Math.cos(next)*radius,ay+Math.sin(next)*radius,...c)}
    }else lineValues.push(ax,ay,...c,mx,my,...c,mx,my,...c,bx,by,...c)
    if((detailed||focused.size<=64&&focused.has(edge.id)||message.selectionId===edge.id)&&['transformer','trafo','trafo3w'].includes(edge.kind))pointValues.push(mx,my,18,2,...color(focused.has(edge.id),true,edge))
    if(edge.state){
      for(const marker of edge.terminalStates||[]){const terminal=index.nodeIds.get(marker.nodeId);if(terminal!==undefined)pointValues.push(index.positions[terminal*2],index.positions[terminal*2+1],12,sceneGlyphs.disconnected.code,...c)}
      if(!edge.terminalStates?.length)pointValues.push(mx,my,12,edge.state==='unresolved'?sceneGlyphs.unresolved.code:sceneGlyphs.disconnected.code,...c)
    }
  }
  const pixelHeight=message.height||message.pixels*.6,labelBudget=Math.max(1,Math.min(100,Math.floor(message.pixels*pixelHeight/14000)))
  const occupied:{x:number;y:number;width:number}[]=[]
  const picked=index.nodeIds.get(message.selectionId||'')
  const orderedNodes=[...(picked!==undefined&&nodes.has(picked)?[picked]:[]),...[...nodes].filter(i=>i!==picked&&focused.has(index.scene.nodes[i].id)),...[...nodes].filter(i=>i!==picked&&!focused.has(index.scene.nodes[i].id))]
  const labelColumns=Math.max(1,Math.ceil(Math.sqrt(labelBudget*message.pixels/pixelHeight))),labelRows=Math.ceil(labelBudget/labelColumns)
  const representatives=new Map<string,{index:number;distance:number}>(),selectedLabels:number[]=[]
  for(const i of orderedNodes){
    const node=index.scene.nodes[i],x=index.positions[i*2],y=index.positions[i*2+1],selected=focused.has(node.id)
    const emphasis=message.selectionId===node.id||selected&&focused.size<=64
    const kind=networkSymbol(node.kind).code
    const size=emphasis?20:detailed?regional?near&&!near.nodeIds.has(node.id)?5:8:kind===1?18:kind===2?20:kind===0?7:14:Math.max(1,Math.min(3,Math.sqrt(message.pixels*pixelHeight/Math.max(1,nodes.size))*.5))
    const tint=regional?(selected?[.12,.32,.63,1]:near&&!near.nodeIds.has(node.id)?[.52,.6,.65,.25]:[.32,.42,.48,1]):color(selected,true,node)
    if(node.boundary)pointValues.push(x,y,size+10,sceneGlyphs.boundaryHalo.code,...tint)
    pointValues.push(x,y,size,node.state==='unresolved'?sceneGlyphs.unresolved.code:detailed||emphasis?kind:0,...tint)
    const px=(x-message.camera.x)/scale,py=(y-message.camera.y)/scale
    if((!near||near.nodeIds.has(node.id))&&px>=0&&py>=0&&px<=message.pixels&&py<=pixelHeight){
      const column=Math.min(labelColumns-1,Math.floor(px/message.pixels*labelColumns)),row=Math.min(labelRows-1,Math.floor(py/pixelHeight*labelRows)),key=`${column}:${row}`
      const distance=(px-(column+.5)*message.pixels/labelColumns)**2+(py-(row+.5)*pixelHeight/labelRows)**2
      if(!representatives.has(key)||representatives.get(key)!.distance>distance)representatives.set(key,{index:i,distance})
      if(emphasis)selectedLabels.push(i)
    }
  }
  const labelCandidates=[...new Set([...selectedLabels,...[...representatives.values()].map(value=>value.index)])]
  for(const i of labelCandidates){
    const node=index.scene.nodes[i],x=index.positions[i*2],y=index.positions[i*2+1]
    if(labels.length<labelBudget){
      const px=(x-message.camera.x)/scale,py=(y-message.camera.y)/scale
      let width=0;for(const char of node.label.slice(0,80))width+=char.charCodeAt(0)>255?12:7
      width=Math.min(180,width)
      const placements=[[8,-18],[-width-8,-18],[8,6],[-width-8,6]]
      for(const [dx,dy] of placements){
        const left=px+dx,top=py+dy
        if(left<0||top<0||left+width>message.pixels||top+18>pixelHeight)continue
        if(occupied.some(box=>left<box.x+box.width+8&&left+width+8>box.x&&top<box.y+22&&top+22>box.y))continue
        labels.push({id:node.id,label:node.label,x,y,dx,dy});occupied.push({x:left,y:top,width});break
      }
    }
  }
  return {type:'frame',request:message.request,lines:Float32Array.from(lineValues),points:Float32Array.from(pointValues),labels,drawnNodes:nodes.size,drawnEdges,representedEdges,bundledGroups:renderedBundles.size,limited:viewport.limited}
}
// The module can be imported by focused tests without installing a Worker global.
const context=typeof self!=='undefined'&&typeof document==='undefined'?self as unknown as {postMessage:(message:unknown,transfer?:Transferable[])=>void;onmessage:((event:MessageEvent<SceneWorkerRequest>)=>void)|null}:undefined
let index:SceneIndex|undefined
if(context)context.onmessage=(event:MessageEvent<SceneWorkerRequest>)=>{
  const message=event.data
  try{
    if(message.type==='load'){
      const started=performance.now();index=buildSceneIndex(message.scene,message.aspect)
      context.postMessage({type:'ready',bounds:index.bounds,stats:{nodes:index.scene.nodes.length,edges:index.scene.edges.length,indexMs:performance.now()-started,bufferBytes:index.positions.byteLength+index.endpoints.byteLength+index.edgeOffsets.byteLength+index.incidentOffsets.byteLength+index.incidentEdges.byteLength}})
    }else if(index){
      if(message.type==='view'){const frame=sceneFrame(index,message);context.postMessage(frame,[frame.lines.buffer,frame.points.buffer])}
      else if(message.type==='pick'){const item=pickPresentedScene(index,message.x,message.y,message.tolerance,message);context.postMessage({type:'selected',request:message.request,item,related:related(index,item)})}
      else if(message.type==='search')context.postMessage({type:'search',request:message.request,results:searchScene(index,message.query)})
      else if(message.type==='locate'){const located=selection(index,message.id);context.postMessage({type:'located',request:message.request,...located,related:related(index,located?.item)})}
      else if(message.type==='focus')context.postMessage({type:'focused',request:message.request,camera:focusScene(index,message.ids,message.markersOnly)})
    }
  }catch(error){context.postMessage({type:'error',message:error instanceof Error?error.message:'Topology renderer failed'})}
}
