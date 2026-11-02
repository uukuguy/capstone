import {pickScene,type SceneIndex} from './networkSceneIndex'
import type {SceneBundle,SceneSelection} from './networkScene'
export type ScenePresentation={bundleParallel?:boolean;expandedBundles?:readonly string[];selectionId?:string;neighborhood?:boolean}
export function bundleSelection(index:SceneIndex,id:string):SceneBundle|undefined{
  const members=index.bundles.get(id);if(!members?.length)return
  const first=index.scene.edges[members[0]]
  return {type:'bundle',id,label:`并行回路束 · ${members.length} 条源线路`,kind:'parallel_circuits',source:first.source,target:first.target,memberIds:members.map(i=>index.scene.edges[i].id),members:members.slice(0,50).map(i=>{const edge=index.scene.edges[i];return {id:edge.id,label:edge.label||edge.id,kind:edge.kind,type:'edge'}})}
}
export function sceneNeighborhood(index:SceneIndex,id:string){
  const node=index.nodeIds.get(id),nodeIds=new Set<string>(),edgeIds=new Set<string>()
  if(node===undefined)return {nodeIds,edgeIds}
  nodeIds.add(id)
  for(let cursor=index.incidentOffsets[node];cursor<index.incidentOffsets[node+1];cursor++){
    const edge=index.incidentEdges[cursor],record=index.scene.edges[edge]
    edgeIds.add(record.id);nodeIds.add(record.source);nodeIds.add(record.target)
  }
  return {nodeIds,edgeIds}
}
export function presentedBundle(index:SceneIndex,edge:number,options:ScenePresentation):string|undefined{
  if(index.scene.displayMode!=='source-regional'||options.bundleParallel===false)return
  const key=index.bundleByEdge.get(edge)
  if(!key||options.expandedBundles?.includes(key))return
  if(options.selectionId&&index.bundles.get(key)?.some(i=>index.scene.edges[i].id===options.selectionId))return
  return key
}
export function pickPresentedScene(index:SceneIndex,x:number,y:number,tolerance:number,options:ScenePresentation={}):SceneSelection|undefined{
  const near=index.scene.displayMode==='source-detail'&&options.neighborhood!==false&&options.selectionId&&index.nodeIds.has(options.selectionId)?sceneNeighborhood(index,options.selectionId):undefined
  const picked=pickScene(index,x,y,tolerance,edge=>presentedBundle(index,edge,options)?0:index.edgeOffsets[edge],near?id=>near.nodeIds.has(id)||near.edgeIds.has(id):undefined)
  if(picked?.type==='edge'){
    const key=presentedBundle(index,index.edgeIds.get(picked.id)!,options)
    if(key)return bundleSelection(index,key)
  }
  return picked
}
