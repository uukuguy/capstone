import type {NetworkScene,SceneCamera,ScenePoint} from './networkScene'

export type ElectricalGeometry={routes:Map<number,ScenePoint[]>;busbars:Map<number,ScenePoint[]>}
const bus=(kind:string)=>['bus','busbar','busbars','busbar_section'].includes(kind)
/** Bounded source layout. Anchors are display coordinates, never source terminals. */
export function electricalSourceLayout(scene:NetworkScene,endpoints:Uint32Array,bounds:SceneCamera,positions:Float32Array):ElectricalGeometry {
  const neighbors=scene.nodes.map(()=>[] as number[])
  scene.edges.forEach((edge,i)=>{if(edge.relation==='connection'){const a=endpoints[2*i],b=endpoints[2*i+1];neighbors[a].push(b);neighbors[b].push(a)}})
  const partitions=new Map<string,number[]>()
  scene.nodes.forEach((node,i)=>{
    // Unique adjacent declarations guide placement only. Shared junctions retain
    // a separate partition, and no derived station is written into source records.
    const stations=new Set(neighbors[i].map(n=>scene.nodes[n].stationId).filter(value=>value!==undefined))
    const voltages=new Set(neighbors[i].map(n=>scene.nodes[n].voltageKv).filter(value=>value!==undefined&&value!==null))
    const station=node.stationId??(stations.size===1?[...stations][0]:null),voltage=node.voltageKv??(voltages.size===1?[...voltages][0]:null)
    const key=JSON.stringify([station,voltage]);const group=partitions.get(key)||[];group.push(i);partitions.set(key,group)
  })
  const groups=[...partitions.entries()].sort(([a],[b])=>a.localeCompare(b)),columns=Math.max(1,Math.ceil(Math.sqrt(groups.length*bounds.width/bounds.height)))
  const cellW=bounds.width/columns,cellH=bounds.height/Math.max(1,Math.ceil(groups.length/columns)),busbars=new Map<number,ScenePoint[]>(),routes=new Map<number,ScenePoint[]>()
  groups.forEach(([,members],groupIndex)=>{
    const left=bounds.x+groupIndex%columns*cellW+cellW*.08,top=bounds.y+Math.floor(groupIndex/columns)*cellH+cellH*.08,width=cellW*.84,height=cellH*.84
    const sorted=members.slice().sort((a,b)=>scene.nodes[a].id.localeCompare(scene.nodes[b].id)),bars=sorted.filter(i=>bus(scene.nodes[i].kind)),remaining=sorted.filter(i=>!bus(scene.nodes[i].kind))
    const memberSet=new Set(members),visited=new Set(bars),order:number[]=[],queue=bars.slice()
    for(let cursor=0;cursor<queue.length;cursor++)for(const next of neighbors[queue[cursor]])if(memberSet.has(next)&&!visited.has(next)){visited.add(next);queue.push(next);order.push(next)}
    order.push(...remaining.filter(i=>!visited.has(i)))
    bars.forEach((i,rank)=>{const y=top+height*.2*(rank+1)/Math.max(1,bars.length);positions[i*2]=left+width/2;positions[i*2+1]=y;busbars.set(i,[{x:left,y},{x:left+width,y}])})
    const lanes=Math.max(1,Math.ceil(Math.sqrt(order.length))),rows=Math.max(1,Math.ceil(order.length/lanes))
    order.forEach((i,rank)=>{positions[i*2]=left+(rank%lanes+.5)*width/lanes;positions[i*2+1]=top+height*(bars.length?.35:.05)+(Math.floor(rank/lanes)+.5)*height*(bars.length?.6:.9)/rows})
  })
  const attachments=new Map<number,number[]>(),parallel=new Map<string,number[]>()
  scene.edges.forEach((edge,i)=>{for(const n of [endpoints[2*i],endpoints[2*i+1]])if(busbars.has(n)){const list=attachments.get(n)||[];list.push(i);attachments.set(n,list)}const key=[edge.source,edge.target].sort().join('\u0000');const list=parallel.get(key)||[];list.push(i);parallel.set(key,list)})
  const anchors=new Map<string,ScenePoint>()
  for(const [n,edges] of attachments){edges.sort((a,b)=>scene.edges[a].id.localeCompare(scene.edges[b].id));const [a,b]=busbars.get(n)!;edges.forEach((e,rank)=>anchors.set(`${n}:${e}`,{x:a.x+(b.x-a.x)*(rank+1)/(edges.length+1),y:a.y}))}
  for(const edges of parallel.values())edges.sort((a,b)=>scene.edges[a].id.localeCompare(scene.edges[b].id)).forEach((e,rank)=>{
    const a=endpoints[2*e],b=endpoints[2*e+1],start=anchors.get(`${a}:${e}`)||{x:positions[2*a],y:positions[2*a+1]},end=anchors.get(`${b}:${e}`)||{x:positions[2*b],y:positions[2*b+1]}
    const lane=(start.y+end.y)/2+(rank-(edges.length-1)/2)*8
    routes.set(e,a===b?[start,{x:start.x+12+rank*8,y:start.y},{x:start.x+12+rank*8,y:start.y+16},{x:start.x,y:start.y+16},end]:[start,{x:start.x,y:lane},{x:end.x,y:lane},end])
  })
  return {routes,busbars}
}
