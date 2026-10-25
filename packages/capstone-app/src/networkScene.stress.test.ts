import {expect,it} from 'vitest'
import {buildSceneIndex,pickScene,queryScene,searchScene} from './networkSceneIndex'
import {sceneFrame} from './networkScene.worker'
import type {NetworkScene} from './networkScene'
it.each(['electrical','source-regional'] as const)('indexes and queries a 120000-node,239300-edge %s scene with bounded geometry and labels',mode=>{
  const count=120000,columns=400
  const scene:NetworkScene={ref:'synthetic-120k',coordinateSystem:'schematic',displayMode:mode,nodes:Array.from({length:count},(_,i)=>({id:`n${i}`,label:`Node ${i}`,kind:'bus',x:i%columns,y:Math.floor(i/columns)})),edges:[]}
  const edges=[]
  for(let i=0;i<count;i++){
    if(i%columns<columns-1)edges.push({id:`h${i}`,source:`n${i}`,target:`n${i+1}`,kind:'line'})
    if(i<count-columns)edges.push({id:`v${i}`,source:`n${i}`,target:`n${i+columns}`,kind:i%1000===0?'transformer':'line'})
  }
  scene.edges=edges
  const started=performance.now(),index=buildSceneIndex(scene),indexed=performance.now()
  const frame=sceneFrame(index,{type:'view',request:1,camera:{x:0,y:0,width:1000,height:600},pixels:1000,focusIds:['n119999']}),framed=performance.now()
  const detail=queryScene(index,{x:400,y:250,width:30,height:18}),queried=performance.now()
  expect(frame.drawnNodes).toBeLessThanOrEqual(24001)
  expect(frame.drawnEdges).toBeLessThanOrEqual(40000)
  expect(frame.labels.length).toBeLessThanOrEqual(100)
  expect(frame.limited).toBe(true)
  expect(detail.nodeIndices.length).toBeLessThan(1000)
  const target=119999
  expect(pickScene(index,index.positions[target*2],index.positions[target*2+1],.01)?.id).toBe('n119999')
  expect(searchScene(index,'n119999')[0].id).toBe('n119999')
  console.info(JSON.stringify({case:'synthetic-120k-index',nodes:count,edges:edges.length,indexMs:indexed-started,frameMs:framed-indexed,detailQueryMs:queried-framed,pointBytes:frame.points.byteLength,lineBytes:frame.lines.byteLength}))
},20000)
