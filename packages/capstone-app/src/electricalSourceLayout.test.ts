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
