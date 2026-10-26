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
})
