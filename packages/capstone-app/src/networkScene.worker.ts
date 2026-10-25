import {buildSceneIndex,focusScene,pickScene,queryScene,searchScene,type SceneIndex} from './networkSceneIndex'
import type {NetworkScene,SceneCamera,SceneSelection} from './networkScene'

export type SceneWorkerRequest=
  |{type:'load';scene:NetworkScene}
  |{type:'view';request:number;camera:SceneCamera;pixels:number;focusIds:readonly string[]}
  |{type:'pick';request:number;x:number;y:number;tolerance:number}
  |{type:'search';request:number;query:string}
  |{type:'locate';request:number;id:string}
  |{type:'focus';request:number;ids:readonly string[];markersOnly?:boolean}
type Label={id:string;label:string;x:number;y:number}
export type SceneFrame={type:'frame';request:number;lines:Float32Array;points:Float32Array;labels:Label[];drawnNodes:number;drawnEdges:number;limited:boolean}
const color=(selected:boolean,node=false,style?:{color?:readonly number[];state?:string})=>selected?[.12,.32,.63,1]:style?.state==='warning'?[.76,.39,.12,1]:style?.state==='disconnected'?[.65,.33,.25,1]:style?.color?[...style.color,1]:node?[.28,.43,.44,1]:[.48,.58,.60,.65]
function selection(index:SceneIndex,id:string):{item:SceneSelection;x:number;y:number}|undefined {
  const node=index.nodeIds.get(id)
  if(node!==undefined)return {item:{type:'node',...index.scene.nodes[node]},x:index.positions[node*2],y:index.positions[node*2+1]}
  const edge=index.edgeIds.get(id)
  if(edge===undefined)return
  const a=index.endpoints[edge*2]*2,b=index.endpoints[edge*2+1]*2
  return {item:{type:'edge',...index.scene.edges[edge]},x:(index.positions[a]+index.positions[b])/2,y:(index.positions[a+1]+index.positions[b+1])/2}
}
export function sceneFrame(index:SceneIndex,message:Extract<SceneWorkerRequest,{type:'view'}>):SceneFrame {
  const viewport=queryScene(index,message.camera),focused=new Set(message.focusIds)
  const nodes=new Set(viewport.nodeIndices),edges=new Set(viewport.edgeIndices)
  for(const id of focused){const n=index.nodeIds.get(id),e=index.edgeIds.get(id);if(n!==undefined)nodes.add(n);if(e!==undefined)edges.add(e)}
  const lineValues:number[]=[],pointValues:number[]=[],labels:Label[]=[]
  const scale=message.camera.width/Math.max(1,message.pixels)
  for(const i of edges){
    const edge=index.scene.edges[i],a=index.endpoints[i*2]*2,b=index.endpoints[i*2+1]*2,ax=index.positions[a],ay=index.positions[a+1],bx=index.positions[b],by=index.positions[b+1]
    const dx=bx-ax,dy=by-ay,length=Math.hypot(dx,dy)||1,offset=index.edgeOffsets[i]
    const mx=(ax+bx)/2-dy/length*offset,my=(ay+by)/2+dx/length*offset,c=color(focused.has(edge.id),false,edge)
    if(a===b){
      const radius=8+Math.abs(index.edgeOffsets[i])
      for(let segment=0;segment<16;segment++){const first=segment*Math.PI/8,next=(segment+1)*Math.PI/8;lineValues.push(ax+Math.cos(first)*radius,ay+Math.sin(first)*radius,...c,ax+Math.cos(next)*radius,ay+Math.sin(next)*radius,...c)}
    }else lineValues.push(ax,ay,...c,mx,my,...c,mx,my,...c,bx,by,...c)
    if(['transformer','trafo','trafo3w'].includes(edge.kind))pointValues.push(mx,my,18,2,...color(focused.has(edge.id),true,edge))
    if(edge.state){
      for(const marker of edge.terminalStates||[]){const terminal=index.nodeIds.get(marker.nodeId);if(terminal!==undefined)pointValues.push(index.positions[terminal*2],index.positions[terminal*2+1],12,3,...c)}
      if(!edge.terminalStates?.length)pointValues.push(mx,my,12,edge.state==='unresolved'?6:3,...c)
    }
  }
  // Pixel cells impose a label budget independently from the graph's object count.
  const labelCells=new Set<string>()
  const orderedNodes=[...nodes].filter(i=>focused.has(index.scene.nodes[i].id)).concat([...nodes].filter(i=>!focused.has(index.scene.nodes[i].id)))
  for(const i of orderedNodes){
    const node=index.scene.nodes[i],x=index.positions[i*2],y=index.positions[i*2+1],selected=focused.has(node.id)
    const kind=node.kind==='bus'?1:node.kind==='switch'?3:node.kind==='station'||node.kind==='voltage_group'?4:node.kind==='boundary'?5:0
    pointValues.push(x,y,selected?16:node.kind==='bus'?14:9,node.state==='unresolved'?6:kind,...color(selected,true,node))
    const cell=`${Math.floor((x-message.camera.x)/scale/110)}:${Math.floor((y-message.camera.y)/scale/28)}`
    if((selected||!labelCells.has(cell))&&labels.length<100){labels.push({id:node.id,label:node.label,x,y});labelCells.add(cell)}
  }
  return {type:'frame',request:message.request,lines:Float32Array.from(lineValues),points:Float32Array.from(pointValues),labels,drawnNodes:nodes.size,drawnEdges:edges.size,limited:viewport.limited}
}
// The module can be imported by focused tests without installing a Worker global.
const context=typeof self!=='undefined'&&typeof document==='undefined'?self as unknown as {postMessage:(message:unknown,transfer?:Transferable[])=>void;onmessage:((event:MessageEvent<SceneWorkerRequest>)=>void)|null}:undefined
let index:SceneIndex|undefined
if(context)context.onmessage=(event:MessageEvent<SceneWorkerRequest>)=>{
  const message=event.data
  try{
    if(message.type==='load'){
      const started=performance.now();index=buildSceneIndex(message.scene)
      context.postMessage({type:'ready',stats:{nodes:index.scene.nodes.length,edges:index.scene.edges.length,indexMs:performance.now()-started,bufferBytes:index.positions.byteLength+index.endpoints.byteLength+index.edgeOffsets.byteLength}})
    }else if(index){
      if(message.type==='view'){const frame=sceneFrame(index,message);context.postMessage(frame,[frame.lines.buffer,frame.points.buffer])}
      else if(message.type==='pick')context.postMessage({type:'selected',request:message.request,item:pickScene(index,message.x,message.y,message.tolerance)})
      else if(message.type==='search')context.postMessage({type:'search',request:message.request,results:searchScene(index,message.query)})
      else if(message.type==='locate')context.postMessage({type:'located',request:message.request,...selection(index,message.id)})
      else if(message.type==='focus')context.postMessage({type:'focused',request:message.request,camera:focusScene(index,message.ids,message.markersOnly)})
    }
  }catch(error){context.postMessage({type:'error',message:error instanceof Error?error.message:'Topology renderer failed'})}
}
