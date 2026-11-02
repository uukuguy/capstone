import {expect,it} from 'vitest'
import {sceneFrame} from './networkScene.worker'
import {buildSceneIndex,focusScene,searchScene} from './networkSceneIndex'
it('keeps hidden technical labels searchable without drawing them even when selected',()=>{
  const index=buildSceneIndex({ref:'labels',coordinateSystem:'schematic',nodes:[
    {id:'node:123456789',label:'node:123456789',kind:'connection_node',showLabel:false,x:0,y:0},
    {id:'bus:1',label:'一号母线',kind:'bus',x:100,y:0}],edges:[]})
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,height:600,focusIds:['node:123456789'],selectionId:'node:123456789'})
  expect(frame.labels.some(label=>label.id==='node:123456789')).toBe(false)
  expect(frame.labels.some(label=>label.label==='一号母线')).toBe(true)
  expect(searchScene(index,'node:123456789')[0].id).toBe('node:123456789')
})
it('fits sparse non-overlapping label rectangles to a narrow viewport instead of drawing100 labels',()=>{
  const scene={ref:'narrow',coordinateSystem:'schematic' as const,nodes:Array.from({length:405},(_,i)=>({id:`n${i}`,label:`站点名称 ${i}`,kind:'station'})),edges:Array.from({length:404},(_,i)=>({id:`e${i}`,source:`n${i}`,target:`n${i+1}`,kind:'line'}))}
  const index=buildSceneIndex(scene,.8),frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:320,height:400,focusIds:[]})
  expect(frame.labels.length).toBeGreaterThan(0)
  expect(frame.labels.length).toBeLessThanOrEqual(9)
  const boxes=frame.labels.map(label=>({x:label.x/index.bounds.width*320+label.dx,y:label.y/index.bounds.height*400+label.dy,width:Math.min(180,4*12+String(label.id.slice(1)).length*7+7)}))
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i],b=boxes[j]
    expect(a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+18&&a.y+18>b.y).toBe(false)
  }
})
it('frames branch terminals and admitted marker-only attention differently',()=>{
  const index=buildSceneIndex({ref:'fault',coordinateSystem:'schematic',nodes:[{id:'a',kind:'bus',label:'A',x:0,y:0},{id:'b',kind:'bus',label:'B',x:100,y:0}],edges:[{id:'e',source:'a',target:'b',kind:'line',terminalStates:[{nodeId:'a',label:'Disconnected'}]}]})
  expect(focusScene(index,['e']).width).toBeGreaterThan(focusScene(index,['e'],true).width)
})
it('returns the actual portrait bounds when a task has no locatable attention IDs',()=>{
  const index=buildSceneIndex({ref:'portrait',coordinateSystem:'schematic',nodes:[{id:'a',kind:'station',label:'A'}],edges:[]},.8)
  expect(focusScene(index,[])).toEqual(index.bounds)
})
it('keeps geometry bounded even when a task references more objects than the visible budget',()=>{
  const nodes=Array.from({length:25000},(_,i)=>({id:`n${i}`,label:`Node ${i}`,kind:'bus',x:i%200,y:Math.floor(i/200)}))
  const index=buildSceneIndex({ref:'many-focused',coordinateSystem:'schematic',nodes,edges:[]})
  const frame=sceneFrame(index,{type:'view',request:1,camera:index.bounds,pixels:1000,focusIds:nodes.map(node=>node.id),selectionId:'n24999'})
  expect(frame.drawnNodes).toBeLessThanOrEqual(24064)
  expect(frame.labels.some(label=>label.id==='n24999')).toBe(true)
})
