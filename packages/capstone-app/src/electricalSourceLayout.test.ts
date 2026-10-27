import {describe,it,expect} from 'vitest'
import {buildSceneIndex,sceneGeometry,pickScene,queryScene,focusScene} from './networkSceneIndex'
import type {NetworkScene} from './networkScene'
import {sceneFrame,sourceNeighborhoodCamera} from './networkScene.worker'

const scene:NetworkScene={ref:'source:fixture',coordinateSystem:'schematic',displayMode:'source-electrical',nodes:[
  {id:'bus-a',label:'Bus A',kind:'busbar',stationId:'s'}, {id:'bus-b',label:'Bus B',kind:'busbar',stationId:'s'},
  {id:'breaker',label:'Breaker',kind:'breaker',stationId:'s',switchState:'unknown'},
  {id:'junction',label:'Junction',kind:'connection_node'},
  {id:'generator',label:'Generator',kind:'generator'}, {id:'load',label:'Load',kind:'load'},
  {id:'transformer',label:'Transformer',kind:'transformer'}, {id:'winding',label:'Winding',kind:'winding'},
],edges:[
  {id:'a',source:'bus-a',target:'breaker',kind:'source_connection',relation:'connection'},
  {id:'b',source:'bus-b',target:'breaker',kind:'source_connection',relation:'connection'},
  {id:'parallel-1',source:'breaker',target:'junction',kind:'source_connection',relation:'connection'},
  {id:'parallel-2',source:'breaker',target:'junction',kind:'source_connection',relation:'connection'},
  {id:'member',source:'transformer',target:'winding',kind:'winding_membership',relation:'membership'},
]}
describe('source electrical geometry',()=>{
  it('keeps a 543-record station with explicit device ports in one bounded display component',()=>{
    const nodes:Array<NetworkScene['nodes'][number]>=[{id:'bus',label:'Bus',kind:'busbar',stationId:'station'},
      {id:'bus-port',label:'',kind:'port',parentId:'bus'},{id:'bus-node',label:'',kind:'connection_node'}]
    const edges:Array<NetworkScene['edges'][number]>=[{id:'bus-owner',source:'bus',target:'bus-port',kind:'port_ownership',relation:'membership'},
      {id:'bus-connection',source:'bus-port',target:'bus-node',kind:'source_connection',relation:'connection'}]
    for(let i=0;i<135;i++){
      const id=`switch-${String(i).padStart(3,'0')}`
      nodes.push({id,label:id,kind:'breaker',stationId:'station'},
        {id:`${id}-a`,label:'',kind:'port',parentId:id},{id:`${id}-b`,label:'',kind:'port',parentId:id},
        {id:`${id}-node`,label:'',kind:'connection_node'})
      edges.push({id:`${id}-owner-a`,source:id,target:`${id}-a`,kind:'port_ownership',relation:'membership'},
        {id:`${id}-owner-b`,source:id,target:`${id}-b`,kind:'port_ownership',relation:'membership'},
        {id:`${id}-connection-a`,source:`${id}-a`,target:'bus-node',kind:'source_connection',relation:'connection'},
        {id:`${id}-connection-b`,source:`${id}-b`,target:`${id}-node`,kind:'source_connection',relation:'connection'})
    }
    const input:NetworkScene={...scene,nodes,edges},original=JSON.stringify(input)
    expect(nodes).toHaveLength(543)
    const index=buildSceneIndex(input),geometry=sceneGeometry(index)!,bar=geometry.busbars.get(0)!
    expect(bar[1].x-bar[0].x).toBeLessThan(index.bounds.width*.2)
    for(let n=0;n<nodes.length;n++)if(nodes[n].kind==='port'){const owner=index.nodeIds.get(nodes[n].parentId!)!;expect(Math.hypot(index.positions[n*2]-index.positions[owner*2],index.positions[n*2+1]-index.positions[owner*2+1])).toBeLessThan(25);expect(geometry.symbolRadii.get(n)!).toBeLessThan(1)}
    expect(geometry.routes.size).toBe(edges.length)
    expect(JSON.stringify(input)).toBe(original)
    expect(index.nodeIds.size).toBe(543)
    assertClear(input)
    const smallNodes=nodes.slice(0,499),smallIds=new Set(smallNodes.map(node=>node.id))
    const smaller=buildSceneIndex({...input,nodes:smallNodes,edges:edges.filter(edge=>smallIds.has(edge.source)&&smallIds.has(edge.target))})
    const smallBar=sceneGeometry(smaller)!.busbars.get(0)!
    expect(bar[1].x-bar[0].x).toBeCloseTo(smallBar[1].x-smallBar[0].x)
  })
  const assertClear=(input:NetworkScene)=>{
    const index=buildSceneIndex(input),geometry=sceneGeometry(index)!
    for(const [e,route] of geometry.routes)for(let n=0;n<input.nodes.length;n++){
      if(n===index.endpoints[e*2]||n===index.endpoints[e*2+1])continue
      const bar=geometry.busbars.get(n),radius=geometry.symbolRadii.get(n)||0
      const left=bar?bar[0].x:index.positions[n*2]-radius,right=bar?bar[1].x:index.positions[n*2]+radius,top=bar?bar[0].y:index.positions[n*2+1]-radius,bottom=bar?bar[0].y:index.positions[n*2+1]+radius
      for(let s=1;s<route.length;s++){const p=route[s-1],q=route[s];expect(Math.max(p.x,q.x)>=left&&Math.min(p.x,q.x)<=right&&Math.max(p.y,q.y)>=top&&Math.min(p.y,q.y)<=bottom,`${input.edges[e].id} crosses ${input.nodes[n].id}`).toBe(false)}
    }
  }
  it('routes around an isolated middle symbol and all unrelated busbar spans',()=>{
    const nodes=Array.from({length:9},(_,i)=>({id:`n${i}`,label:`N${i}`,kind:'breakers'}))
    assertClear({...scene,nodes,edges:[{id:'skip-middle',source:'n0',target:'n2',kind:'source_connection',relation:'connection'}]})
    assertClear(scene)
  })
  it('allocates local component area by records rather than giving every isolated device a full cell',()=>{
    const nodes=[{id:'bus',label:'Bus',kind:'busbar'},...Array.from({length:20},(_,i)=>({id:`connected${i}`,label:'Connected',kind:'breaker'})),...Array.from({length:10},(_,i)=>({id:`isolated${i}`,label:'Isolated',kind:'breaker'}))]
    const edges=Array.from({length:20},(_,i)=>({id:`edge${i}`,source:i%5?`connected${i-1}`:'bus',target:`connected${i}`,kind:'source_connection',relation:'connection' as const}))
    const input:NetworkScene={...scene,nodes,edges},index=buildSceneIndex(input),geometry=sceneGeometry(index)!,bar=geometry.busbars.get(0)!
    expect(bar[1].x-bar[0].x).toBeGreaterThan(index.bounds.width*.5)
    const connected=[...geometry.symbolRadii].filter(([i])=>i>0&&i<=20).map(([,radius])=>radius).sort((a,b)=>a-b),isolated=[...geometry.symbolRadii].filter(([i])=>i>20).map(([,radius])=>radius).sort((a,b)=>a-b)
    expect(connected[10]/isolated[5]).toBeGreaterThan(.5)
    expect(connected[10]/isolated[5]).toBeLessThan(2)
    expect(index.nodeIds.size).toBe(31);expect(geometry.routes.size).toBe(20)
    for(let n=21;n<31;n++)expect(index.incidentOffsets[n+1]-index.incidentOffsets[n]).toBe(0)
    assertClear(input)
  })
  it('validates the final fallback against existing routes in a dense 12-node scene',()=>{
    const pairs=[[5,7],[2,4],[2,3],[8,11],[6,2],[1,10],[8,0],[5,9],[4,5],[6,7],[3,11],[2,0],[1,4],[3,6],[5,11],[0,7],[10,4]]
    const id=(n:number)=>`n${String(n).padStart(2,'0')}`
    const input:NetworkScene={...scene,nodes:Array.from({length:12},(_,i)=>({id:id(i),label:id(i),kind:i<2?'busbar':i%3===0?'connection_node':'breaker'})),edges:pairs.map(([a,b],i)=>({id:`edge${i}`,source:id(a),target:id(b),kind:'source_connection',relation:'connection'}))}
    const geometry=sceneGeometry(buildSceneIndex(input))!
    expect(geometry.routes.size).toBe(pairs.length)
    for(const [e,a] of geometry.routes)for(const [f,b] of geometry.routes)if(e<f&&!pairs[e].some(n=>pairs[f].includes(n)))for(let i=1;i<a.length;i++)for(let j=1;j<b.length;j++){
      const p=a[i-1],q=a[i],r=b[j-1],s=b[j],vertical=p.x===q.x&&r.x===s.x&&p.x===r.x,horizontal=p.y===q.y&&r.y===s.y&&p.y===r.y
      const overlap=vertical?Math.min(Math.max(p.y,q.y),Math.max(r.y,s.y))-Math.max(Math.min(p.y,q.y),Math.min(r.y,s.y)):horizontal?Math.min(Math.max(p.x,q.x),Math.max(r.x,s.x))-Math.max(Math.min(p.x,q.x),Math.min(r.x,s.x)):0
      expect(overlap,`edges ${e} and ${f}`).toBeLessThanOrEqual(0)
    }
    assertClear(input)
  })
  it('packs a local source component despite incomplete station and voltage metadata',()=>{
    const input:NetworkScene={...scene,nodes:[{id:'bus',kind:'busbars',label:'Bus',stationId:'s'},{id:'junction',kind:'connection_node',label:'Junction',voltageKv:500},{id:'switch',kind:'breakers',label:'Switch',stationId:'s'},{id:'high',kind:'windings',label:'High winding',stationId:'s'},{id:'transformer',kind:'transformers',label:'Transformer',stationId:'s'},{id:'low',kind:'windings',label:'Low winding',stationId:'s'},{id:'low-node',kind:'connection_node',label:'Low junction',voltageKv:66}],edges:[{id:'b-j',source:'bus',target:'junction',kind:'source_connection',relation:'connection'},{id:'j-s',source:'junction',target:'switch',kind:'source_connection',relation:'connection'},{id:'s-h',source:'switch',target:'high',kind:'source_connection',relation:'connection'},{id:'t-h',source:'transformer',target:'high',kind:'winding_membership',relation:'membership'},{id:'t-l',source:'transformer',target:'low',kind:'winding_membership',relation:'membership'},{id:'l-n',source:'low',target:'low-node',kind:'source_connection',relation:'connection'}]}
    const index=buildSceneIndex(input),geometry=sceneGeometry(index)!,bar=geometry.busbars.get(0)!
    expect(bar[1].x-bar[0].x).toBeGreaterThan(index.bounds.width*.8)
    expect([...geometry.routes.values()].every(route=>route.length<=6)).toBe(true)
    expect(input.nodes[1].stationId).toBeUndefined();expect(input.nodes[6].voltageKv).toBe(66)
    expect(input.edges.filter(edge=>edge.relation==='membership')).toHaveLength(2)
    assertClear(input)
  })
  it('does not join two disconnected busbar branches in a fallback trunk',()=>{
    const input:NetworkScene={...scene,nodes:[...['bus-a','bus-b','bus-obstacle'].map(id=>({id,label:id,kind:'busbars'})),...['a','b'].map(id=>({id,label:id,kind:'breakers'})),...Array.from({length:496},(_,i)=>({id:`isolated${i}`,label:'Isolated',kind:'load'}))],edges:[{id:'branch-a',source:'bus-a',target:'a',kind:'source_connection',relation:'connection'},{id:'branch-b',source:'bus-b',target:'b',kind:'source_connection',relation:'connection'}]}
    const geometry=sceneGeometry(buildSceneIndex(input))!,a=geometry.routes.get(0)!,b=geometry.routes.get(1)!
    expect(a.length).toBeGreaterThan(4);expect(b.length).toBeGreaterThan(4)
    for(let i=1;i<a.length;i++)for(let j=1;j<b.length;j++){
      const p=a[i-1],q=a[i],r=b[j-1],s=b[j]
      const vertical=p.x===q.x&&r.x===s.x&&p.x===r.x,horizontal=p.y===q.y&&r.y===s.y&&p.y===r.y
      const overlap=vertical?Math.min(Math.max(p.y,q.y),Math.max(r.y,s.y))-Math.max(Math.min(p.y,q.y),Math.min(r.y,s.y)):horizontal?Math.min(Math.max(p.x,q.x),Math.max(r.x,s.x))-Math.max(Math.min(p.x,q.x),Math.min(r.x,s.x)):0
      expect(overlap).toBeLessThanOrEqual(0)
    }
    assertClear(input)
  })
  it('places real feeder depth below busbars and keeps membership-only devices separate',()=>{
    const index=buildSceneIndex({...scene,nodes:['busbars','breakers','disconnectors','windings'].map((kind,i)=>({id:`n${i}`,label:kind,kind})),edges:[{id:'a',source:'n0',target:'n1',kind:'source_connection',relation:'connection'},{id:'b',source:'n1',target:'n2',kind:'source_connection',relation:'connection'},{id:'m',source:'n0',target:'n3',kind:'winding_membership',relation:'membership'},{id:'self',source:'n2',target:'n2',kind:'source_connection',relation:'connection'}]})
    expect(index.positions[1]).toBeLessThan(index.positions[3]);expect(index.positions[3]).toBeLessThan(index.positions[5]);expect(index.positions[5]).toBeLessThan(index.positions[7])
    const loop=sceneGeometry(index)!.routes.get(3)!
    for(let i=1;i<loop.length;i++)expect(loop[i].x===loop[i-1].x||loop[i].y===loop[i-1].y).toBe(true)
  })
  it('preserves all records, isolated devices, and orthogonal real routes',()=>{
    const index=buildSceneIndex(scene),geometry=sceneGeometry(index)!
    expect(index.scene).toBe(scene);expect(geometry.routes.size).toBe(scene.edges.length);expect(geometry.busbars.size).toBe(2)
    for(const route of geometry.routes.values())for(let i=1;i<route.length;i++)expect(route[i].x===route[i-1].x||route[i].y===route[i-1].y).toBe(true)
    expect(scene.nodes[3].stationId).toBeUndefined();expect(index.incidentOffsets[5]-index.incidentOffsets[4]).toBe(0)
    expect([...index.positions]).toEqual([...buildSceneIndex(scene).positions])
    expect(geometry.routes.get(2)).not.toEqual(geometry.routes.get(3))
  })
  it('picks and culls busbar spans and every routed segment; focus contains routes',()=>{
    const index=buildSceneIndex(scene),geometry=sceneGeometry(index)!,bar=geometry.busbars.get(0)!
    expect(pickScene(index,bar[0].x+1,bar[0].y,2)?.id).toBe('bus-a')
    for(const [i,route] of geometry.routes){
      const camera=focusScene(index,[scene.edges[i].id])
      for(const point of route){expect(point.x).toBeGreaterThanOrEqual(camera.x);expect(point.x).toBeLessThanOrEqual(camera.x+camera.width);expect(point.y).toBeGreaterThanOrEqual(camera.y);expect(point.y).toBeLessThanOrEqual(camera.y+camera.height)}
      for(let s=1;s<route.length;s++){const x=(route[s-1].x+route[s].x)/2,y=(route[s-1].y+route[s].y)/2;expect([...queryScene(index,{x:x-.1,y:y-.1,width:.2,height:.2}).edgeIndices]).toContain(i);expect(pickScene(index,x,y,1,undefined,id=>id===scene.edges[i].id)?.id).toBe(scene.edges[i].id)}
    }
  })
  it('lays out 100K nodes without a global force layout',()=>{
    const large:NetworkScene={...scene,nodes:Array.from({length:100000},(_,i)=>({id:String(i),label:String(i),kind:i%100===0?'busbar':'breaker',stationId:String(Math.floor(i/1000)),voltageKv:110})),edges:[]}
    const index=buildSceneIndex(large);expect(index.nodeIds.size).toBe(100000);expect([...index.positions].every(Number.isFinite)).toBe(true)
  })
  it('draws membership with gaps while real routes remain continuous and selection frames the full route',()=>{
    const index=buildSceneIndex(scene),geometry=sceneGeometry(index)!
    const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,focusIds:[]})
    const segments=Array.from({length:frame.lines.length/12},(_,i)=>[frame.lines[i*12],frame.lines[i*12+1],frame.lines[i*12+6],frame.lines[i*12+7]])
    const actual=geometry.routes.get(0)!,member=geometry.routes.get(4)!
    expect(segments).toContainEqual([actual[0].x,actual[0].y,actual[1].x,actual[1].y].map(Math.fround))
    expect(segments).not.toContainEqual([member[1].x,member[1].y,member[2].x,member[2].y].map(Math.fround))
    const camera=sourceNeighborhoodCamera(index,'parallel-1')!
    for(const point of geometry.routes.get(2)!){expect(point.x).toBeGreaterThanOrEqual(camera.x);expect(point.x).toBeLessThanOrEqual(camera.x+camera.width)}
  })
  it('bounds nonempty dense parallel membership buffers and clips offscreen route lengths',()=>{
    const dense:NetworkScene={...scene,nodes:[{id:'a',label:'A',kind:'windings'},{id:'b',label:'B',kind:'transformers'}],edges:Array.from({length:5000},(_,i)=>({id:`m${i}`,source:'a',target:'b',kind:'winding_membership',relation:'membership'}))}
    const index=buildSceneIndex(dense),frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,focusIds:[]})
    expect(frame.lines.length).toBeLessThanOrEqual(120000*12);expect(frame.limited).toBe(true)
    const camera={x:400,y:200,width:10,height:10},zoom=sceneFrame(index,{type:'view',request:2,camera,pixels:1000,focusIds:[]})
    expect(zoom.lines.length).toBeLessThanOrEqual(120000*12)
    for(let i=0;i<zoom.lines.length;i+=6){expect(zoom.lines[i]).toBeGreaterThanOrEqual(camera.x);expect(zoom.lines[i]).toBeLessThanOrEqual(camera.x+camera.width);expect(zoom.lines[i+1]).toBeGreaterThanOrEqual(camera.y);expect(zoom.lines[i+1]).toBeLessThanOrEqual(camera.y+camera.height)}
  })
})
