import type {NetworkScene,SceneCamera,ScenePoint} from './networkScene'

export type ElectricalGeometry={routes:Map<number,ScenePoint[]>;busbars:Map<number,ScenePoint[]>;symbolRadii:Map<number,number>}
const bus=(kind:string)=>['bus','busbar','busbars','busbar_section'].includes(kind)
/** Bounded source layout. Anchors are display coordinates, never source terminals. */
export function electricalSourceLayout(scene:NetworkScene,endpoints:Uint32Array,bounds:SceneCamera,positions:Float32Array,placementOnly=false):ElectricalGeometry {
  const neighbors=scene.nodes.map(()=>[] as number[])
  scene.edges.forEach((edge,i)=>{if(edge.relation==='connection'){const a=endpoints[2*i],b=endpoints[2*i+1];neighbors[a].push(b);neighbors[b].push(a)}})
  // Ports and junctions are separate source records, not separate equipment.
  // Keep ordinary station closures local without sending large networks through
  // the weighted/component layout. These are display-only work budgets.
  const equipment=scene.nodes.filter(node=>!['port','connection_node'].includes(node.kind)).length
  const local=scene.nodes.length<=1500&&scene.edges.length<=3000&&equipment<=500,displayNeighbors=local?scene.nodes.map(()=>[] as Array<{node:number;cost:number}>):[]
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
    const key=local?(displayNeighbors[i].length?String(components[i]):'isolated'):JSON.stringify([station,voltage]);const group=partitions.get(key)||[];group.push(i);partitions.set(key,group)
  })
  const groups=[...partitions.entries()].sort(([a,aa],[b,bb])=>(local?bb.length-aa.length:0)||a.localeCompare(b)),columns=Math.max(1,Math.min(groups.length,Math.ceil(Math.sqrt(groups.length*bounds.width/bounds.height))))
  const cellW=bounds.width/columns,cellH=bounds.height/Math.max(1,Math.ceil(groups.length/columns)),busbars=new Map<number,ScenePoint[]>(),routes=new Map<number,ScenePoint[]>()
  const cells=new Map<string,SceneCamera>(),groupWidths=new Float64Array(scene.nodes.length)
  if(local){
    // Area follows record count, not component count. Isolated records share a
    // display grid; no electrical relationship is added between them.
    const packed=Array.from({length:columns},()=>({groups:[] as typeof groups,weight:0}))
    for(const group of groups){const column=packed.reduce((a,b)=>a.weight<=b.weight?a:b);column.groups.push(group);column.weight+=group[1].length}
    let x=bounds.x
    for(const column of packed){const width=bounds.width*column.weight/Math.max(1,scene.nodes.length);let y=bounds.y
      for(const [key,members] of column.groups){const height=bounds.height*members.length/column.weight;cells.set(key,{x,y,width,height});y+=height}x+=width
    }
  }
  const symbolRadii=new Map<number,number>(),escapes=new Map<number,ScenePoint[]>(),obstacles:{node:number;left:number;right:number;top:number;bottom:number}[]=[]
  groups.forEach(([key,members],groupIndex)=>{
    const cell=cells.get(key)||{x:bounds.x+groupIndex%columns*cellW,y:bounds.y+Math.floor(groupIndex/columns)*cellH,width:cellW,height:cellH}
    const groupW=cell.width,groupH=cell.height,left=cell.x+groupW*.08,top=cell.y+groupH*.08,width=groupW*.84,height=groupH*.84,connectedGroup=local&&key!=='isolated'
    for(const n of members)groupWidths[n]=groupW
    const sorted=members.slice().sort((a,b)=>scene.nodes[a].id.localeCompare(scene.nodes[b].id)),bars=sorted.filter(i=>bus(scene.nodes[i].kind)),remaining=sorted.filter(i=>!bus(scene.nodes[i].kind))
    const memberSet=new Set(members),visited=new Set(bars),order:number[]=[],queue=bars.slice(),depth=new Map(bars.map(n=>[n,0]))
    for(let cursor=0;cursor<queue.length;cursor++)for(const next of neighbors[queue[cursor]])if(memberSet.has(next)&&!visited.has(next)){visited.add(next);depth.set(next,depth.get(queue[cursor])!+1);queue.push(next);order.push(next)}
    if(connectedGroup){
      depth.clear();order.length=0
      const roots=bars.length?bars:[sorted.slice().sort((a,b)=>displayNeighbors[b].length-displayNeighbors[a].length||scene.nodes[a].id.localeCompare(scene.nodes[b].id))[0]]
      const layers:number[][]=[roots];for(const n of roots)depth.set(n,0)
      for(let d=0;d<layers.length;d++)for(const n of layers[d]||[])if(depth.get(n)===d)for(const next of displayNeighbors[n])if(memberSet.has(next.node)&&(!depth.has(next.node)||depth.get(next.node)!>d+next.cost)){const target=d+next.cost;depth.set(next.node,target);while(layers.length<=target)layers.push([]);layers[target].push(next.node)}
      for(const n of remaining)if(depth.has(n))order.push(n)
      order.sort((a,b)=>depth.get(a)!-depth.get(b)!||scene.nodes[a].id.localeCompare(scene.nodes[b].id))
      for(const n of order)visited.add(n)
    }
    order.push(...remaining.filter(i=>!visited.has(i)))
    const outside=left+width+groupW*.04
    bars.forEach((i,rank)=>{const y=top+height*.2*(rank+1)/Math.max(1,bars.length);positions[i*2]=left+width/2;positions[i*2+1]=y;busbars.set(i,[{x:left,y},{x:left+width,y}]);escapes.set(i,[{x:outside,y:y+height*.07/Math.max(1,bars.length)},{x:outside,y:top-groupH*.04}]);obstacles.push({node:i,left,right:left+width,top:y-1,bottom:y+1})})
    const lanes=Math.max(1,Math.ceil(Math.sqrt(order.length))),levels:number[][]=[]
    // Large views use connection depth. Bounded local views also use weighted
    // membership for display placement, without changing relation semantics.
    if(bars.length||connectedGroup){for(const n of order)if(depth.has(n)){const row=Math.max(0,depth.get(n)!-(bars.length?1:0));while(levels.length<=row)levels.push([]);levels[row].push(n)}}
    const isolated=order.filter(n=>(!bars.length&&!connectedGroup)||!depth.has(n))
    for(let i=0;i<isolated.length;i+=lanes)levels.push(isolated.slice(i,i+lanes))
    if(connectedGroup){
      for(let i=levels.length-1;i>=0;i--)if(!levels[i].length)levels.splice(i,1)
      const rank=new Map<number,number>();levels.forEach(nodes=>nodes.forEach((n,i)=>rank.set(n,(i+.5)/nodes.length)))
      for(let pass=0;pass<6;pass++){const rows=pass%2?levels.slice().reverse():levels;for(const nodes of rows){const score=(n:number)=>{const adjacent=displayNeighbors[n].filter(next=>rank.has(next.node));return adjacent.length?adjacent.reduce((sum,next)=>sum+rank.get(next.node)!,0)/adjacent.length:rank.get(n)!};nodes.sort((a,b)=>score(a)-score(b)||scene.nodes[a].id.localeCompare(scene.nodes[b].id));nodes.forEach((n,i)=>rank.set(n,(i+.5)/nodes.length))}}
    }
    // A high-degree source junction can put hundreds of terminals in one BFS
    // level. Wrap that level rather than shrinking every glyph to a subpixel.
    // The source graph and each original endpoint remain unchanged.
    if(connectedGroup&&(members.length>500||placementOnly)){
      const maxColumns=Math.max(1,Math.ceil(Math.sqrt(order.length*width/height)))
      const wrapped:number[][]=[]
      for(const level of levels)for(let i=0;i<level.length;i+=maxColumns)wrapped.push(level.slice(i,i+maxColumns))
      levels.splice(0,levels.length,...wrapped)
    }
    const pitchY=height*(bars.length?.6:.9)/Math.max(1,levels.length)
    levels.forEach((nodes,row)=>nodes.forEach((i,column)=>{const pitchX=width/Math.max(1,nodes.length),x=left+(column+.5)*pitchX,y=top+height*(bars.length?.35:.05)+(row+.5)*pitchY,radius=Math.min(11,pitchX*.18,pitchY*.18);positions[i*2]=x;positions[i*2+1]=y;symbolRadii.set(i,radius);escapes.set(i,[{x:x+pitchX*.4,y},{x:x+pitchX*.4,y:y+pitchY*.4},{x:outside,y:y+pitchY*.4},{x:outside,y:top-groupH*.04}]);obstacles.push({node:i,left:x-radius,right:x+radius,top:y-radius,bottom:y+radius})}))
  })
  if(placementOnly)return {routes,busbars,symbolRadii}
  const ids=new Map(scene.nodes.map((node,i)=>[node.id,i])),owners=new Map<number,number>()
  if(local)scene.nodes.forEach((node,i)=>{const owner=node.parentId?ids.get(node.parentId):undefined;if(node.kind==='port'&&owner!==undefined&&scene.nodes[owner].kind!=='port')owners.set(i,owner)})
  if(owners.size){
    // The proxy exists only to place equipment and explicit source junctions.
    // It is never rendered or returned as electrical connectivity.
    const bodies=scene.nodes.flatMap((_,i)=>owners.has(i)?[]:[i]),proxyIds=new Map(bodies.map((n,i)=>[n,i]))
    const proxyEdges=scene.edges.map((edge,e)=>({...edge,source:scene.nodes[owners.get(endpoints[e*2])??endpoints[e*2]].id,target:scene.nodes[owners.get(endpoints[e*2+1])??endpoints[e*2+1]].id})).filter(edge=>edge.source!==edge.target)
    const proxy:NetworkScene={...scene,nodes:bodies.map(n=>scene.nodes[n]),edges:proxyEdges},proxyNodeIds=new Map(proxy.nodes.map((node,i)=>[node.id,i])),proxyPositions=new Float32Array(bodies.length*2)
    const geometry=electricalSourceLayout(proxy,new Uint32Array(proxyEdges.flatMap(edge=>[proxyNodeIds.get(edge.source)!,proxyNodeIds.get(edge.target)!])),bounds,proxyPositions,true)
    busbars.clear();symbolRadii.clear();obstacles.length=0;escapes.clear()
    for(const n of bodies){const p=proxyIds.get(n)!;positions[n*2]=proxyPositions[p*2];positions[n*2+1]=proxyPositions[p*2+1];symbolRadii.set(n,geometry.symbolRadii.get(p)??6)
      if(bus(scene.nodes[n].kind)){const x=positions[n*2],y=positions[n*2+1];busbars.set(n,[{x:x-18,y},{x:x+18,y}])}}
    const children=new Map<number,number[]>()
    for(const [port,owner] of owners){const list=children.get(owner)||[];list.push(port);children.set(owner,list)}
    for(const [owner,ports] of children){ports.sort((a,b)=>scene.nodes[a].id.localeCompare(scene.nodes[b].id));const radius=symbolRadii.get(owner)!,bar=busbars.get(owner)
      ports.forEach((n,rank)=>{const side=rank%2?-1:1,slot=Math.floor(rank/2),slots=Math.ceil(ports.length/2),pitch=Math.min(2,(bar?30:radius*2)/slots),x=positions[owner*2]+(bar?(slot-(slots-1)/2)*pitch:side*(radius+3)),y=positions[owner*2+1]+(bar?side*4:(slot-(slots-1)/2)*pitch)
        positions[n*2]=x;positions[n*2+1]=y;symbolRadii.set(n,Math.min(.35,pitch*.2))})}
    for(const n of bodies)if(scene.nodes[n].kind==='connection_node'&&neighbors[n].length===1&&neighbors[neighbors[n][0]].length===1){const port=neighbors[n][0],owner=owners.get(port);if(owner!==undefined){positions[n*2]=positions[port*2];positions[n*2+1]=positions[port*2+1]+(symbolRadii.get(owner)!+6);symbolRadii.set(n,.5)}}
    for(let n=0;n<scene.nodes.length;n++){const x=positions[n*2],y=positions[n*2+1],r=symbolRadii.get(n)!,bar=busbars.get(n),reach=owners.has(n)?1.2:Math.max(3,r*1.5)
      groupWidths[n]=bounds.width;escapes.set(n,[{x:x+reach,y:y+3},{x:x+reach,y:y+reach},{x:bounds.x+bounds.width+20,y:bounds.y-4}]);obstacles.push({node:n,left:bar?bar[0].x:x-r,right:bar?bar[1].x:x+r,top:y-(bar?1:r),bottom:y+(bar?1:r)})}
  }
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
  scene.edges.forEach((edge,i)=>{for(const n of new Set([endpoints[2*i],endpoints[2*i+1]])){const list=attachments.get(n)||[];list.push(i);attachments.set(n,list)}const key=[edge.source,edge.target].sort().join('\u0000');const list=parallel.get(key)||[];list.push(i);parallel.set(key,list)})
  const anchors=new Map<string,ScenePoint>()
  const occupied=new Map<string,Map<string,Array<[number,number]>>>()
  const junctions=new Set(scene.nodes.flatMap((node,i)=>node.kind==='connection_node'||bus(node.kind)?[String(i)]:[]))
  const segments=(route:ScenePoint[])=>route.slice(1).map((q,i)=>{const p=route[i],vertical=p.x===q.x;return {key:`${vertical?'x':'y'}:${vertical?p.x:p.y}`,low:Math.min(vertical?p.y:p.x,vertical?q.y:q.x),high:Math.max(vertical?p.y:p.x,vertical?q.y:q.x)}}).filter(segment=>segment.high>segment.low)
  // Common incidence may meet at an explicit source junction/busbar. Devices
  // such as switches are not junctions: never route around their unknown state.
  const overlaps=(route:ScenePoint[],pair:string)=>segments(route).some(segment=>[...(occupied.get(segment.key)||[])].some(([other,intervals])=>other!==pair&&!pair.split(':').some(n=>junctions.has(n)&&other.split(':').includes(n))&&intervals.some(([low,high])=>Math.min(high,segment.high)>Math.max(low,segment.low))))
  const reserve=(route:ScenePoint[],pair:string)=>{for(const segment of segments(route)){const groups=occupied.get(segment.key)||new Map<string,Array<[number,number]>>(),intervals=groups.get(pair)||[];intervals.push([segment.low,segment.high]);groups.set(pair,intervals);occupied.set(segment.key,groups)}}
  const save=(edge:number,route:ScenePoint[],pair:string)=>{const compact=route.filter((p,i)=>!i||p.x!==route[i-1].x||p.y!==route[i-1].y);routes.set(edge,compact);reserve(compact,pair)}
  for(const [n,edges] of attachments){
    const bar=busbars.get(n)
    const other=(e:number)=>endpoints[e*2]===n?endpoints[e*2+1]:endpoints[e*2]
    edges.sort((a,b)=>(bar?0:positions[other(a)*2+1]-positions[other(b)*2+1]||positions[other(a)*2]-positions[other(b)*2])||scene.edges[a].id.localeCompare(scene.edges[b].id))
    edges.forEach((e,rank)=>{
      const other=endpoints[e*2]===n?endpoints[e*2+1]:endpoints[e*2]
      if(bar){const [a,b]=bar;anchors.set(`${n}:${e}`,{x:edges.length===1?Math.max(a.x+4,Math.min(b.x-4,positions[other*2])):a.x+(b.x-a.x)*(rank+1)/(edges.length+1),y:a.y});return}
      if(junctions.has(String(n))||edges.length<2)return
      // Attachment slots stay inside the device glyph. They are display
      // geometry, not invented source ports, terminal roles, or junctions.
      const point={x:positions[n*2],y:positions[n*2+1]+((rank+1)/(edges.length+1)-.5)*Math.min(6,(symbolRadii.get(n)||0)*.5)}
      anchors.set(`${n}:${e}`,point)
      const reach=Math.abs(escapes.get(n)![0].x-point.x)*1.2,pair=[n,other].sort((a,b)=>a-b).join(':')
      if(!owners.size)reserve([{x:point.x-reach,y:point.y},{x:point.x+reach,y:point.y}],pair)
    })
  }
  // Ordinary layouts reserve default lanes up front. Composite terminals use
  // nearby corridors and reserve only accepted routes, avoiding phantom lanes
  // through their owning equipment. Every accepted route is checked below.
  const primaryRoutes=new Map<number,ScenePoint[]>()
  scene.edges.forEach((_,e)=>{
    const fraction=(e+1)/(scene.edges.length+1),factor=.75+fraction*.375
    const escape=(n:number)=>{
      const point=anchors.get(`${n}:${e}`)||{x:positions[n*2],y:positions[n*2+1]},path=escapes.get(n)!,outside=path.at(-1)!.x+groupWidths[n]*(-.03+.06*fraction)
      if(busbars.has(n)){const y=point.y+(path[0].y-point.y)*factor;return [point,{x:point.x,y},{x:outside,y}]}
      const x=positions[n*2]+(path[0].x-positions[n*2])*factor,y=positions[n*2+1]+(path[1].y-positions[n*2+1])*factor
      return [point,{x,y:point.y},{x,y},{x:outside,y}]
    }
    const a=endpoints[2*e],b=endpoints[2*e+1],from=escape(a),to=escape(b),channel=bounds.y-8-fraction*20,x=from.at(-1)!.x
    const bridge=a!==b&&x===to.at(-1)!.x?[]:[{x,y:channel},...(a===b?[{x:x+8,y:channel},{x:x+8,y:channel-8},{x,y:channel-8}]:[]),{x:to.at(-1)!.x,y:channel}]
    const route=[...from,...bridge,...to.reverse()],pair=[a,b].sort((x,y)=>x-y).join(':')
    primaryRoutes.set(e,route);if(!owners.size)reserve(route,pair)
  })
  for(const edges of parallel.values())edges.sort((a,b)=>scene.edges[a].id.localeCompare(scene.edges[b].id)).forEach((e,rank)=>{
    const a=endpoints[2*e],b=endpoints[2*e+1],start=anchors.get(`${a}:${e}`)||{x:positions[2*a],y:positions[2*a+1]},end=anchors.get(`${b}:${e}`)||{x:positions[2*b],y:positions[2*b+1]}
    const lane=(start.y+end.y)/2+(rank-(edges.length-1)/2)*Math.min(8,20/edges.length)
    const direct=[start,{x:start.x,y:lane},{x:end.x,y:lane},end]
    const pair=[a,b].sort((x,y)=>x-y).join(':')
    if(a!==b&&clear(direct,a,b)&&!overlaps(direct,pair)){save(e,direct,pair);return}
    if(a!==b){
      const offset=(rank-(edges.length-1)/2)*Math.min(8,20/edges.length),candidates:ScenePoint[][]=[]
      for(const ratio of [.25,.5,.75]){const x=start.x+(end.x-start.x)*ratio+offset,y=start.y+(end.y-start.y)*ratio+offset;candidates.push([start,{x,y:start.y},{x,y:end.y},end],[start,{x:start.x,y},{x:end.x,y},end])}
      for(let delta of (owners.size?[-24,-12,-4,-2,-1,1,2,4,12,24]:[-24,-12,12,24])){const shift=owners.size?(e+1)/(scene.edges.length+1):0,x=(start.x+end.x)/2+delta+offset+shift;delta+=shift;candidates.push([start,{x:start.x,y:start.y+delta},{x,y:start.y+delta},{x,y:end.y+delta},{x:end.x,y:end.y+delta},end])}
      candidates.sort((a,b)=>{const length=(route:ScenePoint[])=>route.slice(1).reduce((sum,p,i)=>sum+Math.abs(p.x-route[i].x)+Math.abs(p.y-route[i].y),0);return length(a)-length(b)})
      const compact=candidates.find(route=>clear(route,a,b)&&!overlaps(route,pair));if(compact){save(e,compact,pair);return}
    }
    if(owners.size&&a!==b){
      // Composite terminals need short exits before traversing equipment rows.
      // Search a fixed number of display corridors, still checking every route.
      for(const delta of [-.8,.8,-2,2,-5,5,-9,9])for(let column=0;column<64;column++){
        const x=bounds.x+(column+.37)*bounds.width/64,shift=(e+1)/(scene.edges.length+1)*.2
        const route=[start,{x:start.x,y:start.y+delta+shift},{x,y:start.y+delta+shift},{x,y:end.y+delta+shift},{x:end.x,y:end.y+delta+shift},end]
        if(clear(route,a,b)&&!overlaps(route,pair)){save(e,route,pair);return}
      }
    }
    // Each edge has its own horizontal and vertical reserved lanes. A shared
    // perimeter trunk would falsely join circuits with different source nodes.
    const primary=primaryRoutes.get(e)!
    if(clear(primary,a,b)&&!overlaps(primary,pair)){save(e,primary,pair);return}
    const fraction=(e+1)/(scene.edges.length+1),factor=.75+fraction*.375
    const escape=(n:number,point:ScenePoint,outsideSide:number,horizontal:number,vertical:number,verticalFirst:boolean)=>{
      const path=escapes.get(n)!,outside=path.at(-1)!.x+groupWidths[n]*(-.03+.06*fraction)+(outsideSide<0?-groupWidths[n]*.92:0)
      if(busbars.has(n)){const y=point.y+(path[0].y-point.y)*factor*vertical;return [point,{x:point.x,y},{x:outside,y},{x:outside,y:path.at(-1)!.y}]}
      const x=point.x+(path[0].x-point.x)*factor*horizontal,y=point.y+(path[1].y-point.y)*factor*vertical
      return [point,verticalFirst?{x:point.x,y}:{x,y:point.y},{x,y},{x:outside,y},{x:outside,y:path.at(-1)!.y}]
    }
    const exits=(n:number,point:ScenePoint)=>{
      const options:ScenePoint[][]=[]
      for(const verticalFirst of [false,true])for(const outside of [1,-1])for(const horizontal of [1,-1])for(const vertical of [1,-1]){if(busbars.has(n)&&(horizontal<0||verticalFirst))continue;const route=escape(n,point,outside,horizontal,vertical,verticalFirst);if(clear(route,a,b)&&!overlaps(route,pair))options.push(route)}
      return options
    }
    const channel=bounds.y-8-(e+1)/(scene.edges.length+1)*20
    // At most 16 exits per endpoint, hence at most 256 complete candidates.
    // Never publish a final route that bypasses either collision check.
    for(const from of exits(a,start))for(const to of exits(b,end)){
      if(a!==b&&from.at(-1)!.x===to.at(-1)!.x){const perimeter=[...from.slice(0,-1),...to.slice(0,-1).reverse()];if(clear(perimeter,a,b)&&!overlaps(perimeter,pair)){save(e,perimeter,pair);return}}
      const x=from.at(-1)!.x,loop=a===b?[{x:x+8,y:channel},{x:x+8,y:channel-8},{x,y:channel-8}]:[]
      const route=[...from,{x,y:channel},...loop,{x:to.at(-1)!.x,y:channel},...to.slice().reverse()]
      if(clear(route,a,b)&&!overlaps(route,pair)){save(e,route,pair);return}
    }
    throw new Error(`No collision-free source route within the bounded layout: ${scene.edges[e].id}`)
  })
  return {routes,busbars,symbolRadii}
}
