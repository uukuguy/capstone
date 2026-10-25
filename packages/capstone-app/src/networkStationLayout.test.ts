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
it.each(['source-detail','source-regional'] as const)('frames both actual endpoints when locating a long %s edge',displayMode=>{
  const scene:NetworkScene={ref:'long-edge',coordinateSystem:'schematic',displayMode,nodes:[{id:'a',label:'A',kind:'terminal',x:0,y:0},{id:'b',label:'B',kind:'terminal',x:1000,y:0}],edges:[{id:'e',source:'a',target:'b',kind:'source_line'}]}
  const index=buildSceneIndex(scene),camera=sourceNeighborhoodCamera(index,'e')!
  expect(camera).toBeDefined()
  for(let i=0;i<2;i++){
    expect(index.positions[i*2]).toBeGreaterThan(camera.x)
    expect(index.positions[i*2]).toBeLessThan(camera.x+camera.width)
  }
  const frame=sceneFrame(index,{type:'view',request:1,camera,pixels:800,height:480,focusIds:['e'],selectionId:'e'})
  expect(frame.drawnNodes).toBe(2)
  expect(frame.drawnEdges).toBe(1)
})
it('fits the actual common endpoints of a source-only line bundle',()=>{
  const index=buildSceneIndex({ref:'long-bundle',coordinateSystem:'schematic',displayMode:'source-regional',nodes:[{id:'a',label:'A',kind:'station',x:0,y:0},{id:'b',label:'B',kind:'station',x:1000,y:0}],edges:[{id:'e1',source:'a',target:'b',kind:'source_line'},{id:'e2',source:'b',target:'a',kind:'source_line'}]})
  const id=[...index.bundles.keys()][0],camera=sourceNeighborhoodCamera(index,id)!
  expect(camera).toBeDefined()
  expect(camera.x).toBeLessThan(index.positions[0])
  expect(camera.x+camera.width).toBeGreaterThan(index.positions[2])
})
it('retains selected edge endpoints even when their station detail is collapsed at the camera scale',()=>{
  const index=buildSceneIndex(stationScene())
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:800,height:480,focusIds:['e0'],selectionId:'e0'})
  expect(frame.drawnNodes).toBeGreaterThanOrEqual(2)
  expect(frame.drawnEdges).toBeGreaterThanOrEqual(1)
})
