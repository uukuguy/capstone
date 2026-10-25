import type {NetworkScene,SceneCamera,SceneSearchResult,SceneSelection} from './networkScene'
type Box={minX:number;minY:number;maxX:number;maxY:number}
type Tree=Box&{count:number;indices?:number[];left?:Tree;right?:Tree}
export type SceneIndex={scene:NetworkScene;bounds:SceneCamera;positions:Float32Array;endpoints:Uint32Array;edgeOffsets:Float32Array;nodeIds:Map<string,number>;edgeIds:Map<string,number>;nodes:Tree;edges:Tree;search:{key:string;result:SceneSearchResult}[]}
const intersects=(a:Box,b:Box)=>a.minX<=b.maxX&&a.maxX>=b.minX&&a.minY<=b.maxY&&a.maxY>=b.minY
function tree(indices:number[],box:(index:number)=>Box):Tree {
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
  for(const index of indices){const b=box(index);minX=Math.min(minX,b.minX);minY=Math.min(minY,b.minY);maxX=Math.max(maxX,b.maxX);maxY=Math.max(maxY,b.maxY)}
  const root:Tree={minX,minY,maxX,maxY,count:indices.length}
  if(indices.length<=32){root.indices=indices;return root}
  const x=maxX-minX>=maxY-minY
  indices.sort((a,b)=>{const aa=box(a),bb=box(b);return x?aa.minX+aa.maxX-bb.minX-bb.maxX:aa.minY+aa.maxY-bb.minY-bb.maxY})
  const middle=indices.length>>>1
  root.left=tree(indices.slice(0,middle),box);root.right=tree(indices.slice(middle),box)
  return root
}
const nodeBox=(positions:Float32Array,index:number):Box=>({minX:positions[index*2],maxX:positions[index*2],minY:positions[index*2+1],maxY:positions[index*2+1]})
function edgeBox(index:SceneIndex,i:number):Box {
  const a=index.endpoints[i*2]*2,b=index.endpoints[i*2+1]*2
  const padding=Math.abs(index.edgeOffsets[i])+12
  return {minX:Math.min(index.positions[a],index.positions[b])-padding,maxX:Math.max(index.positions[a],index.positions[b])+padding,minY:Math.min(index.positions[a+1],index.positions[b+1])-padding,maxY:Math.max(index.positions[a+1],index.positions[b+1])+padding}
}
export function buildSceneIndex(scene:NetworkScene,aspect=5/3):SceneIndex {
  const height=1000/Math.max(.35,Math.min(4,aspect)),bounds={x:0,y:0,width:1000,height}
  const nodeIds=new Map<string,number>(),edgeIds=new Map<string,number>()
  scene.nodes.forEach((node,i)=>{if(nodeIds.has(node.id))throw new Error('Duplicate topology node ID');nodeIds.set(node.id,i)})
  const endpoints=new Uint32Array(scene.edges.length*2),positions=new Float32Array(scene.nodes.length*2),edgeOffsets=new Float32Array(scene.edges.length)
  const parallel=new Map<string,number[]>()
  scene.edges.forEach((edge,i)=>{
    const from=nodeIds.get(edge.source),to=nodeIds.get(edge.target)
    if(from===undefined||to===undefined||edgeIds.has(edge.id)||nodeIds.has(edge.id))throw new Error('Invalid topology edge identity or endpoint')
    edgeIds.set(edge.id,i);endpoints[i*2]=from;endpoints[i*2+1]=to
    const key=from<to?`${from}:${to}`:`${to}:${from}`
    const group=parallel.get(key)||[];group.push(i);parallel.set(key,group)
  })
  for(const group of parallel.values())group.forEach((edge,i)=>{edgeOffsets[edge]=(i-(group.length-1)/2)*4*(endpoints[edge*2]<=endpoints[edge*2+1]?1:-1)})
  const supplied=scene.nodes.length>0&&scene.nodes.every(node=>typeof node.x==='number'&&Number.isFinite(node.x)&&typeof node.y==='number'&&Number.isFinite(node.y))
  if(supplied){
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
    for(const node of scene.nodes){minX=Math.min(minX,node.x!);maxX=Math.max(maxX,node.x!);minY=Math.min(minY,node.y!);maxY=Math.max(maxY,node.y!)}
    const scale=Math.min(920/Math.max(1,maxX-minX),(height-72)/Math.max(1,maxY-minY))
    scene.nodes.forEach((node,i)=>{positions[i*2]=500+(node.x!-(minX+maxX)/2)*scale;positions[i*2+1]=height/2+(node.y!-(minY+maxY)/2)*scale*(scene.coordinateSystem==='geographic'?-1:1)})
  }else{
    // Linear-time deterministic graph traversal, on the worker rather than the UI thread.
    const neighbors=scene.nodes.map(()=>[] as number[])
    for(let i=0;i<endpoints.length;i+=2){neighbors[endpoints[i]].push(endpoints[i+1]);neighbors[endpoints[i+1]].push(endpoints[i])}
    const visited=new Uint8Array(scene.nodes.length),order:number[]=[]
    for(let start=0;start<scene.nodes.length;start++)if(!visited[start]){
      const queue=[start];visited[start]=1
      for(let cursor=0;cursor<queue.length;cursor++){const n=queue[cursor];order.push(n);for(const next of neighbors[n])if(!visited[next]){visited[next]=1;queue.push(next)}}
    }
    const columns=Math.max(1,Math.ceil(Math.sqrt(scene.nodes.length*aspect))),rows=Math.max(1,Math.ceil(scene.nodes.length/columns))
    order.forEach((node,i)=>{positions[node*2]=40+(i%columns+.5)*920/columns;positions[node*2+1]=36+(Math.floor(i/columns)+.5)*(height-72)/rows})
    if(scene.nodes.length<=1500&&scene.nodes.length>1){
      // Bounded local repulsion plus edge springs exposes the small overview's graph
      // structure. Large detail never enters an all-pairs layout.
      const ideal=Math.sqrt(920*(height-72)/scene.nodes.length),cell=ideal*1.6,forces=new Float32Array(positions.length)
      for(let iteration=0;iteration<100;iteration++){
        forces.fill(0);const cells=new Map<string,number[]>()
        for(let i=0;i<scene.nodes.length;i++){const key=`${Math.floor(positions[i*2]/cell)}:${Math.floor(positions[i*2+1]/cell)}`,items=cells.get(key)||[];items.push(i);cells.set(key,items)}
        for(let i=0;i<scene.nodes.length;i++){
          const x=positions[i*2],y=positions[i*2+1],cx=Math.floor(x/cell),cy=Math.floor(y/cell)
          for(let gx=cx-1;gx<=cx+1;gx++)for(let gy=cy-1;gy<=cy+1;gy++)for(const j of cells.get(`${gx}:${gy}`)||[])if(j>i){
            const dx=x-positions[j*2],dy=y-positions[j*2+1],distance=Math.max(1,Math.hypot(dx,dy)),force=Math.min(20,ideal*ideal/distance*.4)
            forces[i*2]+=dx/distance*force;forces[i*2+1]+=dy/distance*force;forces[j*2]-=dx/distance*force;forces[j*2+1]-=dy/distance*force
          }
        }
        for(let e=0;e<endpoints.length;e+=2){const a=endpoints[e]*2,b=endpoints[e+1]*2,dx=positions[b]-positions[a],dy=positions[b+1]-positions[a+1],distance=Math.max(1,Math.hypot(dx,dy)),force=(distance-ideal*1.2)*.025;forces[a]+=dx/distance*force;forces[a+1]+=dy/distance*force;forces[b]-=dx/distance*force;forces[b+1]-=dy/distance*force}
        const cooling=1-iteration/120
        for(let i=0;i<scene.nodes.length;i++){positions[i*2]=Math.max(40,Math.min(960,positions[i*2]+Math.max(-12,Math.min(12,forces[i*2]))*cooling));positions[i*2+1]=Math.max(36,Math.min(height-36,positions[i*2+1]+Math.max(-12,Math.min(12,forces[i*2+1]))*cooling))}
      }
    }
  }
  const index:SceneIndex={scene,bounds,positions,endpoints,edgeOffsets,nodeIds,edgeIds,nodes:null!,edges:null!,search:[]}
  index.nodes=tree(scene.nodes.map((_,i)=>i),i=>nodeBox(positions,i))
  index.edges=tree(scene.edges.map((_,i)=>i),i=>edgeBox(index,i))
  index.search=[...scene.nodes.map(node=>({key:`${node.id} ${node.label}`.toLocaleLowerCase(),result:{id:node.id,label:node.label,kind:node.kind,type:'node' as const}})),
    ...scene.edges.map(edge=>({key:`${edge.id} ${edge.label||''}`.toLocaleLowerCase(),result:{id:edge.id,label:edge.label||edge.id,kind:edge.kind,type:'edge' as const}}))]
  return index
}
export function queryScene(index:SceneIndex,camera:SceneCamera,nodeLimit=24000,edgeLimit=40000){
  const box={minX:camera.x,minY:camera.y,maxX:camera.x+camera.width,maxY:camera.y+camera.height}
  let limited=false
  function query(root:Tree,limit:number,itemBox:(i:number)=>Box){
    const found:number[]=[]
    function visit(node:Tree,budget:number){
      if(!intersects(node,box))return
      if(budget<=0){limited=true;return}
      if(node.indices){
        const candidates=node.indices.filter(i=>intersects(itemBox(i),box)),count=Math.min(candidates.length,budget)
        if(count<candidates.length)limited=true
        for(let rank=0;rank<count;rank++)found.push(candidates[Math.floor(rank*candidates.length/count)])
      }else{
        const left=intersects(node.left!,box),right=intersects(node.right!,box)
        const leftBudget=left&&right?Math.round(budget*node.left!.count/node.count):left?budget:0
        if(left)visit(node.left!,leftBudget)
        if(right)visit(node.right!,budget-leftBudget)
      }
    }
    visit(root,limit);return Uint32Array.from(found)
  }
  return {nodeIndices:query(index.nodes,nodeLimit,i=>nodeBox(index.positions,i)),edgeIndices:query(index.edges,edgeLimit,i=>edgeBox(index,i)),limited}
}
function boxDistance(box:Box,x:number,y:number){const dx=Math.max(box.minX-x,0,x-box.maxX),dy=Math.max(box.minY-y,0,y-box.maxY);return dx*dx+dy*dy}
export function pickScene(index:SceneIndex,x:number,y:number,tolerance:number):SceneSelection|undefined {
  let best=tolerance*tolerance,selected:SceneSelection|undefined
  function visit(root:Tree,node:boolean){
    if(boxDistance(root,x,y)>best)return
    if(root.indices)for(const i of root.indices){
      let distance:number
      if(node){distance=(index.positions[i*2]-x)**2+(index.positions[i*2+1]-y)**2}
      else{
        const a=index.endpoints[i*2]*2,b=index.endpoints[i*2+1]*2,ax=index.positions[a],ay=index.positions[a+1],bx=index.positions[b],by=index.positions[b+1]
        const length=Math.hypot(bx-ax,by-ay)
        if(!length)distance=(Math.hypot(x-ax,y-ay)-(8+Math.abs(index.edgeOffsets[i])))**2
        else{
          const mx=(ax+bx)/2-(by-ay)/length*index.edgeOffsets[i],my=(ay+by)/2+(bx-ax)/length*index.edgeOffsets[i]
          const segment=(sx:number,sy:number,tx:number,ty:number)=>{const squared=(tx-sx)**2+(ty-sy)**2,t=squared?Math.max(0,Math.min(1,((x-sx)*(tx-sx)+(y-sy)*(ty-sy))/squared)):0;return (sx+t*(tx-sx)-x)**2+(sy+t*(ty-sy)-y)**2}
          distance=Math.min(segment(ax,ay,mx,my),segment(mx,my,bx,by))
        }
      }
      if(distance<best){best=distance;selected=node?{type:'node',...index.scene.nodes[i]}:{type:'edge',...index.scene.edges[i]}}
    }else{
      const first=boxDistance(root.left!,x,y)<=boxDistance(root.right!,x,y)?root.left!:root.right!,second=first===root.left?root.right!:root.left!
      visit(first,node);visit(second,node)
    }
  }
  visit(index.nodes,true)
  if(!selected)visit(index.edges,false)
  return selected
}
export function searchScene(index:SceneIndex,query:string,limit=20):SceneSearchResult[]{
  const normalized=query.trim().toLocaleLowerCase();if(!normalized)return []
  const found:SceneSearchResult[]=[]
  for(const entry of index.search)if(entry.key.includes(normalized)){found.push(entry.result);if(found.length>=Math.min(50,limit))break}
  return found
}
export function focusScene(index:SceneIndex,ids:readonly string[],markersOnly=false):SceneCamera {
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
  const add=(i:number)=>{const x=index.positions[i*2],y=index.positions[i*2+1];minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y)}
  for(const id of ids){
    const node=index.nodeIds.get(id),edge=index.edgeIds.get(id)
    if(node!==undefined)add(node)
    if(edge!==undefined){
      const markers=index.scene.edges[edge].terminalStates?.flatMap(marker=>{const i=index.nodeIds.get(marker.nodeId);return i===undefined?[]:[i]})
      if(markersOnly&&markers?.length)markers.forEach(add)
      else{add(index.endpoints[edge*2]);add(index.endpoints[edge*2+1])}
    }
  }
  if(!Number.isFinite(minX))return {...index.bounds}
  const width=Math.min(950,Math.max(380,maxX-minX+250,(maxY-minY+170)*5/3)),height=width*.6
  return {x:(minX+maxX-width)/2,y:(minY+maxY-height)/2,width,height}
}
