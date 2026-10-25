import {expect,it} from 'vitest'
import {buildSceneIndex} from './networkSceneIndex'
import {pickPresentedScene,sceneNeighborhood} from './networkScenePresentation'
import {sceneFrame} from './networkScene.worker'
import type {NetworkScene} from './networkScene'
const scene:NetworkScene={ref:'source-regional',displayMode:'source-regional',coordinateSystem:'schematic',nodes:[{id:'a',label:'A',kind:'station',x:0,y:0},{id:'b',label:'B',kind:'station',x:100,y:0},{id:'c',label:'C',kind:'station',x:1000,y:500},{id:'d',label:'D',kind:'station',x:1100,y:500}],edges:[{id:'ab1',source:'a',target:'b',kind:'source_line'},{id:'ab2',source:'a',target:'b',kind:'source_line'},{id:'cd',source:'c',target:'d',kind:'source_line'}]}
it('bundles only source regional parallel circuits while retaining exact member IDs and expandable picks',()=>{
  const index=buildSceneIndex(scene),message={type:'view' as const,request:1,camera:index.bounds,pixels:1000,focusIds:[]}
  const frame=sceneFrame(index,message)
  expect(frame.drawnEdges).toBe(2)
  expect(frame.representedEdges).toBe(3)
  expect(Array.from({length:frame.lines.length/6},(_,i)=>frame.lines[i*6+5]).every(alpha=>alpha<.3)).toBe(true)
  const x=(index.positions[0]+index.positions[2])/2,y=(index.positions[1]+index.positions[3])/2
  const bundle=pickPresentedScene(index,x,y,1,{bundleParallel:true})
  expect(bundle).toMatchObject({type:'bundle',memberIds:['ab1','ab2']})
  expect(sceneFrame(index,{...message,expandedBundles:[bundle!.id]}).drawnEdges).toBe(3)
  expect(pickPresentedScene(index,x,y+index.edgeOffsets[0],1,{bundleParallel:true,expandedBundles:[bundle!.id]})?.id).toBe('ab1')
  expect(sceneFrame(buildSceneIndex({...scene,displayMode:'electrical'}),message).drawnEdges).toBe(3)
})
it('uses indexed incident source relations to emphasize a selected node without dropping unrelated identities',()=>{
  const index=buildSceneIndex(scene),near=sceneNeighborhood(index,'a')
  expect(near.nodeIds).toEqual(new Set(['a','b']))
  expect(near.edgeIds).toEqual(new Set(['ab1','ab2']))
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,focusIds:['a'],selectionId:'a',neighborhood:true})
  expect(frame.representedEdges).toBe(3)
  expect(frame.labels.every(label=>['a','b'].includes(label.id))).toBe(true)
})
