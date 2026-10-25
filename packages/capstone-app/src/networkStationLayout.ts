import type {NetworkScene,SceneCamera} from './networkScene'

export type StationDisplayGroup={stationId:string|null;label:string;indices:number[];bounds:SceneCamera}

/** Weighted rectangles separate display regions. They are not electrical nodes. */
function partition<T>(items:T[],weight:(item:T)=>number,bounds:SceneCamera,place:(item:T,box:SceneCamera)=>void){
  if(!items.length)return
  if(items.length===1){place(items[0],bounds);return}
  const weights=items.map(weight),total=weights.reduce((a,b)=>a+b,0)
  let split=1,left=weights[0]
  while(split<items.length-1&&left+weights[split]/2<total/2)left+=weights[split++]
  const fraction=left/total
  if(bounds.width>=bounds.height){
    const width=bounds.width*fraction
    partition(items.slice(0,split),weight,{...bounds,width},place)
    partition(items.slice(split),weight,{...bounds,x:bounds.x+width,width:bounds.width-width},place)
  }else{
    const height=bounds.height*fraction
    partition(items.slice(0,split),weight,{...bounds,height},place)
    partition(items.slice(split),weight,{...bounds,y:bounds.y+height,height:bounds.height-height},place)
  }
}
function inset(box:SceneCamera,fraction:number):SceneCamera {
  return {x:box.x+box.width*fraction,y:box.y+box.height*fraction,width:box.width*(1-2*fraction),height:box.height*(1-2*fraction)}
}

/** Exact station_id only. No name matching, inferred station assignment or force iterations.
 * Within each station, BFS layers follow actual source edges in O(nodes + edges).
 * Disconnected source components get separate display cells, without adding edges.
 */
export function layoutStationDetail(scene:NetworkScene,endpoints:Uint32Array,bounds:SceneCamera,positions:Float32Array){
  const byStation=new Map<string|null,number[]>(),neighbors=scene.nodes.map(()=>[] as number[])
  for(let i=0;i<scene.nodes.length;i++){
    const station=scene.nodes[i].stationId||null,indices=byStation.get(station)||[]
    indices.push(i);byStation.set(station,indices)
  }
  for(let e=0;e<endpoints.length;e+=2){
    const a=endpoints[e],b=endpoints[e+1]
    if(a!==b&&(scene.nodes[a].stationId||null)===(scene.nodes[b].stationId||null)){neighbors[a].push(b);neighbors[b].push(a)}
  }
  const labels=new Map(scene.nodes.map(node=>[node.id,node.label]))
  const groups:StationDisplayGroup[]=[...byStation].map(([stationId,indices])=>({stationId,indices,
    label:stationId?labels.get(stationId)||stationId:'未声明站点的源对象',bounds}))
  groups.sort((a,b)=>b.indices.length-a.indices.length||(a.stationId||'').localeCompare(b.stationId||''))
  const seen=new Uint8Array(scene.nodes.length),depth=new Uint32Array(scene.nodes.length)
  partition(groups,group=>group.indices.length+4,bounds,(group,cell)=>{
    group.bounds=inset(cell,.06)
    const components:number[][]=[]
    // Highest degree first makes directly connected equipment visible around its hub.
    const starts=[...group.indices].sort((a,b)=>neighbors[b].length-neighbors[a].length||a-b)
    for(const start of starts)if(!seen[start]){
      const queue=[start];seen[start]=1
      for(let cursor=0;cursor<queue.length;cursor++)for(const next of neighbors[queue[cursor]])if(!seen[next]){
        seen[next]=1;depth[next]=depth[queue[cursor]]+1;queue.push(next)
      }
      components.push(queue)
    }
    components.sort((a,b)=>b.length-a.length||a[0]-b[0])
    partition(components,items=>items.length+1,inset(group.bounds,.08),(items,component)=>{
      const layers=new Map<number,number[]>()
      for(const i of items){const layer=layers.get(depth[i])||[];layer.push(i);layers.set(depth[i],layer)}
      for(const [level,indices] of layers)for(let rank=0;rank<indices.length;rank++){
        positions[indices[rank]*2]=component.x+component.width*(level+.5)/layers.size
        positions[indices[rank]*2+1]=component.y+component.height*(rank+.5)/indices.length
      }
    })
  })
  return groups
}

export function collapsedStation(group:StationDisplayGroup,camera:SceneCamera,pixels:number){
  // Show real elements once the station has enough pixels per member.
  const scale=Math.max(1,pixels)/camera.width
  return group.indices.length>8&&group.bounds.width<camera.width*.75&&group.bounds.height<camera.height*.75
    &&group.bounds.width*group.bounds.height*scale*scale/group.indices.length<225
}
