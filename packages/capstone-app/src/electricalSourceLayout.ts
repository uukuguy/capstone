import type {NetworkScene,SceneCamera,ScenePoint} from './networkScene'

export type ElectricalGeometry={routes:Map<number,ScenePoint[]>;busbars:Map<number,ScenePoint[]>;symbolRadii:Map<number,number>}
const bus=(kind:string)=>['bus','busbar','busbars','busbar_section'].includes(kind)
/** Bounded source layout. Anchors are display coordinates, never source terminals. */
export function electricalSourceLayout(scene:NetworkScene,endpoints:Uint32Array,bounds:SceneCamera,positions:Float32Array):ElectricalGeometry {
  const neighbors=scene.nodes.map(()=>[] as number[])
  scene.edges.forEach((edge,i)=>{if(edge.relation==='connection'){const a=endpoints[2*i],b=endpoints[2*i+1];neighbors[a].push(b);neighbors[b].push(a)}})
  const local=scene.nodes.length<=500,displayNeighbors=local?scene.nodes.map(()=>[] as Array<{node:number;cost:number}>):[]
  if(local)scene.edges.forEach((edge,i)=>{const a=endpoints[2*i],b=endpoints[2*i+1],cost=edge.relation==='connection'?1:3;displayNeighbors[a].push({node:b,cost});displayNeighbors[b].push({node:a,cost})})
  const components=new Int32Array(scene.nodes.length).fill(-1)
  if(local)for(let start=0;start<scene.nodes.length;start++)if(components[start]===-1){const queue=[start];components[start]=start;for(let cursor=0;cursor<queue.length;cursor++)for(const {node} of displayNeighbors[queue[cursor]])if(components[node]===-1){components[node]=start;queue.push(node)}}
  const partitions=new Map<string,number[]>()
  scene.nodes.forEach((node,i)=>{
    // Unique adjacent declarations guide placement only. Shared junctions retain
    // a separate partition, and no derived station is written into source records.
    const stations=new Set(neighbors[i].map(n=>scene.nodes[n].stationId).filter(value=>value!==undefined))
    const voltages=new Set(neighbors[i].map(n=>scene.nodes[n].voltageKv).filter(value=>value!==undefined&&value!==null))
    const station=node.stationId??(stations.size===1?[...stations][0]:null),voltage=node.voltageKv??(voltages.size===1?[...voltages][0]:null)
    // A bounded local diagram packs related source objects together even when
    // ownership/voltage metadata is incomplete. This is display grouping only.
    const key=local?String(components[i]):JSON.stringify([station,voltage]);const group=partitions.get(key)||[];group.push(i);partitions.set(key,group)
  })
  const groups=[...partitions.entries()].sort(([a],[b])=>a.localeCompare(b)),columns=Math.max(1,Math.min(groups.length,Math.ceil(Math.sqrt(groups.length*bounds.width/bounds.height))))
  const cellW=bounds.width/columns,cellH=bounds.height/Math.max(1,Math.ceil(groups.length/columns)),busbars=new Map<number,ScenePoint[]>(),routes=new Map<number,ScenePoint[]>()
  const symbolRadii=new Map<number,number>(),escapes=new Map<number,ScenePoint[]>(),obstacles:{node:number;left:number;right:number;top:number;bottom:number}[]=[]
  groups.forEach(([,members],groupIndex)=>{
    const left=bounds.x+groupIndex%columns*cellW+cellW*.08,top=bounds.y+Math.floor(groupIndex/columns)*cellH+cellH*.08,width=cellW*.84,height=cellH*.84
    const sorted=members.slice().sort((a,b)=>scene.nodes[a].id.localeCompare(scene.nodes[b].id)),bars=sorted.filter(i=>bus(scene.nodes[i].kind)),remaining=sorted.filter(i=>!bus(scene.nodes[i].kind))
    const memberSet=new Set(members),visited=new Set(bars),order:number[]=[],queue=bars.slice(),depth=new Map(bars.map(n=>[n,0]))
    for(let cursor=0;cursor<queue.length;cursor++)for(const next of neighbors[queue[cursor]])if(memberSet.has(next)&&!visited.has(next)){visited.add(next);depth.set(next,depth.get(queue[cursor])!+1);queue.push(next);order.push(next)}
    if(local){
      depth.clear();order.length=0
      const roots=bars.length?bars:[sorted.slice().sort((a,b)=>displayNeighbors[b].length-displayNeighbors[a].length||scene.nodes[a].id.localeCompare(scene.nodes[b].id))[0]]
      const layers:number[][]=[roots];for(const n of roots)depth.set(n,0)
      for(let d=0;d<layers.length;d++)for(const n of layers[d]||[])if(depth.get(n)===d)for(const next of displayNeighbors[n])if(memberSet.has(next.node)&&(!depth.has(next.node)||depth.get(next.node)!>d+next.cost)){const target=d+next.cost;depth.set(next.node,target);while(layers.length<=target)layers.push([]);layers[target].push(next.node)}
      for(const n of remaining)if(depth.has(n))order.push(n)
      order.sort((a,b)=>depth.get(a)!-depth.get(b)!||scene.nodes[a].id.localeCompare(scene.nodes[b].id))
      for(const n of order)visited.add(n)
    }
    order.push(...remaining.filter(i=>!visited.has(i)))
    const outside=left+width+cellW*.04
    bars.forEach((i,rank)=>{const y=top+height*.2*(rank+1)/Math.max(1,bars.length);positions[i*2]=left+width/2;positions[i*2+1]=y;busbars.set(i,[{x:left,y},{x:left+width,y}]);escapes.set(i,[{x:outside,y:y+height*.07/Math.max(1,bars.length)},{x:outside,y:top-cellH*.04}]);obstacles.push({node:i,left,right:left+width,top:y-1,bottom:y+1})})
    const lanes=Math.max(1,Math.ceil(Math.sqrt(order.length))),levels:number[][]=[]
    // Large views use connection depth. Bounded local views also use weighted
    // membership for display placement, without changing relation semantics.
    if(bars.length||local){for(const n of order)if(depth.has(n)){const row=Math.max(0,depth.get(n)!-(bars.length?1:0));while(levels.length<=row)levels.push([]);levels[row].push(n)}}
    const isolated=order.filter(n=>(!bars.length&&!local)||!depth.has(n))
    for(let i=0;i<isolated.length;i+=lanes)levels.push(isolated.slice(i,i+lanes))
    if(local){
      for(let i=levels.length-1;i>=0;i--)if(!levels[i].length)levels.splice(i,1)
      const rank=new Map<number,number>();levels.forEach(nodes=>nodes.forEach((n,i)=>rank.set(n,(i+.5)/nodes.length)))
      for(let pass=0;pass<6;pass++){const rows=pass%2?levels.slice().reverse():levels;for(const nodes of rows){const score=(n:number)=>{const adjacent=displayNeighbors[n].filter(next=>rank.has(next.node));return adjacent.length?adjacent.reduce((sum,next)=>sum+rank.get(next.node)!,0)/adjacent.length:rank.get(n)!};nodes.sort((a,b)=>score(a)-score(b)||scene.nodes[a].id.localeCompare(scene.nodes[b].id));nodes.forEach((n,i)=>rank.set(n,(i+.5)/nodes.length))}}
    }
    const pitchY=height*(bars.length?.6:.9)/Math.max(1,levels.length)
    levels.forEach((nodes,row)=>nodes.forEach((i,column)=>{const pitchX=width/Math.max(1,nodes.length),x=left+(column+.5)*pitchX,y=top+height*(bars.length?.35:.05)+(row+.5)*pitchY,radius=Math.min(11,pitchX*.18,pitchY*.18);positions[i*2]=x;positions[i*2+1]=y;symbolRadii.set(i,radius);escapes.set(i,[{x:x+pitchX*.4,y},{x:x+pitchX*.4,y:y+pitchY*.4},{x:outside,y:y+pitchY*.4},{x:outside,y:top-cellH*.04}]);obstacles.push({node:i,left:x-radius,right:x+radius,top:y-radius,bottom:y+radius})}))
  })
  if(!scene.edges.length)return {routes,busbars,symbolRadii}
  // Spatial buckets keep route checks local; no node-by-edge all-pairs pass.
  const bucketSize=Math.max(bounds.width,bounds.height)/64,buckets=new Map<string,number[]>()
  obstacles.forEach((box,i)=>{for(let x=Math.floor(box.left/bucketSize);x<=Math.floor(box.right/bucketSize);x++)for(let y=Math.floor(box.top/bucketSize);y<=Math.floor(box.bottom/bucketSize);y++){const key=`${x}:${y}`,list=buckets.get(key)||[];list.push(i);buckets.set(key,list)}})
  const clear=(route:ScenePoint[],a:number,b:number)=>{
    for(let s=1;s<route.length;s++){const p=route[s-1],q=route[s],left=Math.min(p.x,q.x),right=Math.max(p.x,q.x),top=Math.min(p.y,q.y),bottom=Math.max(p.y,q.y)
      for(let x=Math.floor(left/bucketSize);x<=Math.floor(right/bucketSize);x++)for(let y=Math.floor(top/bucketSize);y<=Math.floor(bottom/bucketSize);y++)for(const i of buckets.get(`${x}:${y}`)||[]){const box=obstacles[i];if(box.node!==a&&box.node!==b&&left<=box.right&&right>=box.left&&top<=box.bottom&&bottom>=box.top)return false}
    }return true
  }
  const attachments=new Map<number,number[]>(),parallel=new Map<string,number[]>()
  scene.edges.forEach((edge,i)=>{for(const n of [endpoints[2*i],endpoints[2*i+1]])if(busbars.has(n)){const list=attachments.get(n)||[];list.push(i);attachments.set(n,list)}const key=[edge.source,edge.target].sort().join('\u0000');const list=parallel.get(key)||[];list.push(i);parallel.set(key,list)})
  const anchors=new Map<string,ScenePoint>()
  const occupied=new Map<string,Map<string,Array<[number,number]>>>()
  const junctions=new Set(scene.nodes.flatMap((node,i)=>node.kind==='connection_node'||bus(node.kind)?[String(i)]:[]))
  const segments=(route:ScenePoint[])=>route.slice(1).map((q,i)=>{const p=route[i],vertical=p.x===q.x;return {key:`${vertical?'x':'y'}:${vertical?p.x:p.y}`,low:Math.min(vertical?p.y:p.x,vertical?q.y:q.x),high:Math.max(vertical?p.y:p.x,vertical?q.y:q.x)}}).filter(segment=>segment.high>segment.low)
  // Common incidence may meet at an explicit source junction/busbar. Devices
  // such as switches are not junctions: never route around their unknown state.
  const overlaps=(route:ScenePoint[],pair:string)=>segments(route).some(segment=>[...(occupied.get(segment.key)||[])].some(([other,intervals])=>other!==pair&&!pair.split(':').some(n=>junctions.has(n)&&other.split(':').includes(n))&&intervals.some(([low,high])=>Math.min(high,segment.high)>Math.max(low,segment.low))))
  const save=(edge:number,route:ScenePoint[],pair:string)=>{const compact=route.filter((p,i)=>!i||p.x!==route[i-1].x||p.y!==route[i-1].y);routes.set(edge,compact);for(const segment of segments(compact)){const groups=occupied.get(segment.key)||new Map<string,Array<[number,number]>>(),intervals=groups.get(pair)||[];intervals.push([segment.low,segment.high]);groups.set(pair,intervals);occupied.set(segment.key,groups)}}
  for(const [n,edges] of attachments){edges.sort((a,b)=>scene.edges[a].id.localeCompare(scene.edges[b].id));const [a,b]=busbars.get(n)!;edges.forEach((e,rank)=>{const other=endpoints[e*2]===n?endpoints[e*2+1]:endpoints[e*2];anchors.set(`${n}:${e}`,{x:edges.length===1?Math.max(a.x+4,Math.min(b.x-4,positions[other*2])):a.x+(b.x-a.x)*(rank+1)/(edges.length+1),y:a.y})})}
  for(const edges of parallel.values())edges.sort((a,b)=>scene.edges[a].id.localeCompare(scene.edges[b].id)).forEach((e,rank)=>{
    const a=endpoints[2*e],b=endpoints[2*e+1],start=anchors.get(`${a}:${e}`)||{x:positions[2*a],y:positions[2*a+1]},end=anchors.get(`${b}:${e}`)||{x:positions[2*b],y:positions[2*b+1]}
    const lane=(start.y+end.y)/2+(rank-(edges.length-1)/2)*Math.min(8,20/edges.length)
    const direct=[start,{x:start.x,y:lane},{x:end.x,y:lane},end]
    const pair=[a,b].sort((x,y)=>x-y).join(':')
    if(a!==b&&clear(direct,a,b)&&!overlaps(direct,pair)){save(e,direct,pair);return}
    if(a!==b){
      const offset=(rank-(edges.length-1)/2)*Math.min(8,20/edges.length),candidates:ScenePoint[][]=[]
      for(const ratio of [.25,.5,.75]){const x=start.x+(end.x-start.x)*ratio+offset,y=start.y+(end.y-start.y)*ratio+offset;candidates.push([start,{x,y:start.y},{x,y:end.y},end],[start,{x:start.x,y},{x:end.x,y},end])}
      for(const delta of [-24,-12,12,24]){const x=(start.x+end.x)/2+delta+offset;candidates.push([start,{x:start.x,y:start.y+delta},{x,y:start.y+delta},{x,y:end.y+delta},{x:end.x,y:end.y+delta},end])}
      candidates.sort((a,b)=>{const length=(route:ScenePoint[])=>route.slice(1).reduce((sum,p,i)=>sum+Math.abs(p.x-route[i].x)+Math.abs(p.y-route[i].y),0);return length(a)-length(b)})
      const compact=candidates.find(route=>clear(route,a,b)&&!overlaps(route,pair));if(compact){save(e,compact,pair);return}
    }
    // Each edge has its own horizontal and vertical reserved lanes. A shared
    // perimeter trunk would falsely join circuits with different source nodes.
    const fraction=(e+1)/(scene.edges.length+1),factor=.75+fraction*.375
    const escape=(n:number,point:ScenePoint)=>{
      const path=escapes.get(n)!,outside=path.at(-1)!.x+cellW*(-.03+.06*fraction)
      if(busbars.has(n)){const y=point.y+(path[0].y-point.y)*factor;return [point,{x:point.x,y},{x:outside,y},{x:outside,y:path.at(-1)!.y}]}
      const x=point.x+(path[0].x-point.x)*factor,y=point.y+(path[1].y-point.y)*factor
      return [point,{x,y:point.y},{x,y},{x:outside,y},{x:outside,y:path.at(-1)!.y}]
    }
    const from=escape(a,start),to=escape(b,end),channel=bounds.y-8-(e+1)/(scene.edges.length+1)*20
    if(a!==b&&from.at(-1)!.x===to.at(-1)!.x){const perimeter=[...from.slice(0,-1),...to.slice(0,-1).reverse()];if(clear(perimeter,a,b)&&!overlaps(perimeter,pair)){save(e,perimeter,pair);return}}
    const x=from.at(-1)!.x,loop=a===b?[{x:x+8,y:channel},{x:x+8,y:channel-8},{x,y:channel-8}]:[]
    save(e,[...from,{x,y:channel},...loop,{x:to.at(-1)!.x,y:channel},...to.reverse()],pair)
  })
  return {routes,busbars,symbolRadii}
}
