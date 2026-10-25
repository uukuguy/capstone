import {expect,it} from 'vitest'
import {buildSceneIndex} from './networkSceneIndex'
import {sceneFrame,related,sourceNeighborhoodCamera,stationAtPoint} from './networkScene.worker'
import {pickPresentedScene} from './networkScenePresentation'
import type {NetworkScene} from './networkScene'

function stationScene(count=2400):NetworkScene {
  return {ref:'station-detail',displayMode:'source-detail',coordinateSystem:'schematic',
    nodes:Array.from({length:count},(_,i)=>({id:`n${i}`,label:`Object ${i}`,kind:i%20===0?'busbars':'terminal',stationId:`station-${i%12}`})),
    edges:Array.from({length:count-12},(_,i)=>({id:`e${i}`,source:`n${i}`,target:`n${i+12}`,kind:'connection'}))}
}
it('partitions interleaved records by exact source station without changing identities or connections',()=>{
  const scene=stationScene(),index=buildSceneIndex(scene)
  expect(index.stationGroups).toHaveLength(12)
  for(const group of index.stationGroups){
    expect(group.indices.every(i=>scene.nodes[i].stationId===group.stationId)).toBe(true)
    for(const i of group.indices){
      expect(index.positions[i*2]).toBeGreaterThan(group.bounds.x)
      expect(index.positions[i*2]).toBeLessThan(group.bounds.x+group.bounds.width)
    }
  }
  expect(index.nodeIds.size).toBe(scene.nodes.length)
  expect(index.endpoints.length).toBe(scene.edges.length*2)
  expect(index.bundles.size).toBe(0)
})
it('shows station display regions at overview and real equipment when zoomed, without invented edges',()=>{
  const index=buildSceneIndex(stationScene())
  const message={type:'view' as const,request:1,camera:index.bounds,pixels:800,height:480,focusIds:[]}
  const overview=sceneFrame(index,message)
  expect(overview.collapsedStations).toBeGreaterThan(0)
  expect(overview.drawnNodes).toBeLessThan(2400)
  const group=index.stationGroups[0]
  const detail=sceneFrame(index,{...message,camera:group.bounds})
  expect(detail.drawnNodes).toBeGreaterThanOrEqual(group.indices.length)
  expect(detail.drawnEdges).toBeGreaterThan(0)
})
it('keeps unknown station membership explicit and preserves direct-neighbor emphasis in source detail',()=>{
  const scene=stationScene()
  scene.nodes=[...scene.nodes,{id:'unknown',label:'Unassigned',kind:'busbars'}]
  const index=buildSceneIndex(scene)
  expect(index.stationGroups.find(group=>group.stationId===null)?.indices).toEqual([2400])
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:800,height:480,focusIds:['n0'],selectionId:'n0',neighborhood:true})
  expect(frame.labels.every(label=>label.id==='n0'||label.id==='n12'||label.id.startsWith('station-label:'))).toBe(true)
  expect(frame.drawnEdges).toBeGreaterThan(0)
})
it('opens a displayed station region and frames exact adjacent equipment when searching',()=>{
  const scene=stationScene(),index=buildSceneIndex(scene),group=index.stationGroups[0]
  expect(stationAtPoint(index,group.bounds.x+group.bounds.width/2,group.bounds.y+group.bounds.height/2,index.bounds,800)).toEqual(group.bounds)
  const camera=sourceNeighborhoodCamera(index,'n0')!
  expect(camera.width).toBeLessThan(group.bounds.width)
  expect(related(index,{type:'node',...scene.nodes[0]})).toMatchObject({totalNodes:1,edges:1,nodes:[{id:'n12'}]})
})
it('does not pick hidden unrelated equipment while showing a direct neighborhood',()=>{
  const scene=stationScene(),index=buildSceneIndex(scene),hidden=index.nodeIds.get('n100')!
  expect(pickPresentedScene(index,index.positions[hidden*2],index.positions[hidden*2+1],.001,{selectionId:'n0',neighborhood:true})).toBeUndefined()
})
