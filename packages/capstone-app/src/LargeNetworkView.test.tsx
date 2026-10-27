import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import LargeNetworkView from './LargeNetworkView'
import type {NetworkScene} from './networkScene'
const renderGL=vi.hoisted(()=>({draw:vi.fn(),upload:vi.fn(),dispose:vi.fn()}))
vi.mock('./networkWebGL',()=>({createNetworkRenderer:()=>renderGL}))
class TestWorker {
  static instances:TestWorker[]=[]
  onmessage:((event:{data:unknown})=>void)|null=null
  onerror:(()=>void)|null=null
  postMessage=vi.fn();terminate=vi.fn()
  constructor(){TestWorker.instances.push(this)}
  emit(data:unknown){act(()=>this.onmessage?.({data}))}
}
vi.stubGlobal('Worker',TestWorker)
afterEach(()=>{cleanup();TestWorker.instances=[];vi.clearAllMocks();vi.useRealTimers()})
const scene:NetworkScene={ref:'source-view',coordinateSystem:'schematic',nodes:[{id:'station',label:'Source station',kind:'station',details:[{label:'Origin',value:'Source record'}]}],edges:[]}
it('reports the first drawn frame once per scene, after drawing rather than worker readiness',()=>{
  const painted=vi.fn(()=>expect(renderGL.draw).toHaveBeenCalled())
  const ui=render(<LargeNetworkView scene={scene} onFirstFrame={painted}/>)
  const first=TestWorker.instances[0]
  first.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(painted).not.toHaveBeenCalled()
  const frame={type:'frame',request:1,lines:new Float32Array(),points:new Float32Array(),labels:[],drawnNodes:1,drawnEdges:0,limited:false}
  first.emit(frame);first.emit(frame)
  expect(painted).toHaveBeenCalledTimes(1)
  ui.rerender(<LargeNetworkView scene={{...scene,ref:'next'}} onFirstFrame={painted}/>)
  first.emit(frame)
  expect(painted).toHaveBeenCalledTimes(1)
  TestWorker.instances[1].emit(frame)
  expect(painted).toHaveBeenCalledTimes(2)
})
it('uses a worker with typed scene identity and exposes bounded accessible picked details',()=>{
  const onSelect=vi.fn()
  render(<LargeNetworkView scene={scene} onSelect={onSelect}/>)
  const worker=TestWorker.instances[0]
  expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({type:'load',scene}))
  worker.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({type:'view',camera:expect.any(Object)}))
  worker.emit({type:'frame',request:1,lines:new Float32Array(),points:new Float32Array(),labels:[],drawnNodes:1,drawnEdges:0,limited:false})
  worker.emit({type:'selected',request:1,item:{type:'node',...scene.nodes[0]}})
  expect(screen.getByLabelText('所选拓扑对象').textContent).toContain('Source record')
  expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({kind:'station'}))
  expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({type:'view',focusIds:['station']}))
  expect(document.querySelectorAll('canvas')).toHaveLength(1)
  expect(document.querySelectorAll('.large-network-stage svg')).toHaveLength(0)
})
it('terminates obsolete views and ignores their late replies',()=>{
  const ready=vi.fn(),{rerender}=render(<LargeNetworkView scene={scene} onReady={ready}/>)
  const first=TestWorker.instances[0]
  rerender(<LargeNetworkView scene={{...scene,ref:'next-view'}} onReady={ready}/>)
  expect(first.terminate).toHaveBeenCalledOnce()
  first.emit({type:'ready',stats:{nodes:999,edges:0,indexMs:1,bufferBytes:8}})
  expect(ready).not.toHaveBeenCalled()
})
it('debounces search on the worker and never sends the scene again for keyboard camera motion',()=>{
  vi.useFakeTimers()
  render(<LargeNetworkView scene={scene}/>)
  const worker=TestWorker.instances[0]
  worker.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'station'}})
  act(()=>vi.advanceTimersByTime(121))
  expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({type:'search',query:'station'}))
  fireEvent.keyDown(screen.getByRole('img'),{key:'ArrowRight'})
  expect(worker.postMessage.mock.calls.filter(([message])=>message.type==='load')).toHaveLength(1)
})
it('waits for worker and task-layer readiness before consuming a return request exactly once',()=>{
  sessionStorage.setItem('pending-large',JSON.stringify({preview:{x:10,y:10,width:600,height:360}}))
  const props={scene,focusIds:['station'],focusKey:'task',storageKey:'pending-large',viewKey:'preview',returnTaskRequest:1}
  const {rerender}=render(<LargeNetworkView {...props} taskLayerReady={false}/>)
  const first=TestWorker.instances[0]
  first.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(first.postMessage.mock.calls.filter(([message])=>message.type==='focus')).toHaveLength(0)
  rerender(<LargeNetworkView {...props} taskLayerReady/>)
  expect(first.postMessage.mock.calls.filter(([message])=>message.type==='focus')).toHaveLength(1)
  rerender(<LargeNetworkView {...props} taskLayerReady viewKey="later"/>)
  const second=TestWorker.instances[1]
  second.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(second.postMessage.mock.calls.filter(([message])=>message.type==='focus')).toHaveLength(0)
})
it('focuses a newly admitted unsaved scene even when the instruction focus key stays the same',()=>{
  const props={scene,focusIds:['station'],focusKey:'same-instruction'}
  const {rerender}=render(<LargeNetworkView {...props} viewKey="source-one"/>)
  const first=TestWorker.instances[0]
  first.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(first.postMessage.mock.calls.filter(([message])=>message.type==='focus')).toHaveLength(1)
  rerender(<LargeNetworkView {...props} viewKey="source-two"/>)
  const second=TestWorker.instances[1]
  second.emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
  expect(second.postMessage.mock.calls.filter(([message])=>message.type==='focus')).toHaveLength(1)
})
it('preserves camera scale through panel resizing and ignores hidden zero-size canvases',()=>{
  vi.useFakeTimers();let resize!:()=>void
  const previous=globalThis.ResizeObserver
  vi.stubGlobal('ResizeObserver',class{constructor(callback:()=>void){resize=callback}observe(){}disconnect(){}})
  try{
    render(<LargeNetworkView scene={scene}/>)
    const canvas=screen.getByRole('img');let width=1000,height=600
    Object.defineProperties(canvas,{clientWidth:{get:()=>width},clientHeight:{get:()=>height}})
    TestWorker.instances[0].emit({type:'ready',stats:{nodes:1,edges:0,indexMs:1,bufferBytes:8}})
    height=400;act(()=>{resize();vi.advanceTimersByTime(20)})
    expect(renderGL.draw).toHaveBeenLastCalledWith(expect.objectContaining({width:1000,height:400}))
    const calls=renderGL.draw.mock.calls.length
    width=0;height=0;act(()=>{resize();vi.advanceTimersByTime(20)})
    expect(renderGL.draw.mock.calls).toHaveLength(calls)
    width=1000;height=600;act(()=>{resize();vi.advanceTimersByTime(20)})
    expect(renderGL.draw).toHaveBeenLastCalledWith(expect.objectContaining({width:1000,height:600}))
  }finally{vi.stubGlobal('ResizeObserver',previous)}
})
it('keeps regional bundle controls and raw member selection explicit, without activating a fake source object',()=>{
  const onActivate=vi.fn(),regional={...scene,displayMode:'source-regional' as const,edges:[{id:'e1',source:'station',target:'station',kind:'source_line'},{id:'e2',source:'station',target:'station',kind:'source_line'}]}
  render(<LargeNetworkView scene={regional} onActivate={onActivate}/>)
  expect(screen.getByRole('checkbox',{name:'合并并行回路'})).toBeTruthy()
  expect(screen.getByLabelText('拓扑符号图例').textContent).toContain('站点分组')
  const worker=TestWorker.instances[0]
  worker.emit({type:'ready',stats:{nodes:1,edges:2,indexMs:1,bufferBytes:8}})
  worker.emit({type:'frame',request:1,lines:new Float32Array(),points:new Float32Array(),labels:[],drawnNodes:1,drawnEdges:1,representedEdges:2,bundledGroups:1,limited:false})
  worker.emit({type:'selected',request:2,item:{type:'bundle',id:'bundle-test',kind:'parallel_circuits',label:'并行回路束',source:'station',target:'station',memberIds:['e1','e2'],members:[{id:'e1',kind:'source_line',label:'Circuit1',type:'edge'},{id:'e2',kind:'source_line',label:'Circuit2',type:'edge'}]}})
  fireEvent.click(screen.getByRole('button',{name:'展开2条源线路'}))
  expect(onActivate).not.toHaveBeenCalled()
  worker.emit({type:'frame',request:3,lines:new Float32Array(),points:new Float32Array(),labels:[],drawnNodes:1,drawnEdges:1,representedEdges:2,bundledGroups:1,limited:false})
  expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({type:'view',expandedBundles:['bundle-test']}))
  fireEvent.click(screen.getByRole('button',{name:'查看回路：e2'}))
  expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({type:'locate',id:'e2'}))
})
it('renders the exact source-edge count separately from direct-neighbor count',()=>{
  render(<LargeNetworkView scene={{...scene,displayMode:'source-regional'}}/>)
  const worker=TestWorker.instances[0]
  worker.emit({type:'selected',request:1,item:{type:'node',...scene.nodes[0]},related:{nodes:[],totalNodes:2,edges:5}})
  expect(screen.getByLabelText('来源直接关联').textContent).toContain('2 个直接关联对象 · 5 条源线路')
  worker.emit({type:'selected',request:2,item:{type:'node',...scene.nodes[0]},related:{nodes:[],totalNodes:2}})
  expect(screen.getByLabelText('来源直接关联').textContent).not.toContain('·  条源线路')
})
it('supports source-detail direct relationships and frames the worker-provided neighborhood camera',()=>{
  vi.useFakeTimers()
  render(<LargeNetworkView scene={{...scene,displayMode:'source-detail'}}/>)
  expect(screen.getByRole('checkbox',{name:'突出直接关联'})).toBeTruthy()
  expect(screen.queryByRole('checkbox',{name:'合并并行回路'})).toBeNull()
  const worker=TestWorker.instances[0],camera={x:10,y:20,width:8,height:4.8}
  worker.emit({type:'ready',stats:{nodes:1,edges:2,indexMs:1,bufferBytes:8}})
  worker.emit({type:'located',request:1,item:{type:'node',...scene.nodes[0]},camera,related:{nodes:[{id:'next',label:'Next terminal',kind:'terminal',type:'node'}],totalNodes:1,edges:2}})
  act(()=>vi.advanceTimersByTime(20))
  expect(renderGL.draw).toHaveBeenLastCalledWith(camera)
  expect(screen.getByLabelText('来源直接关联').textContent).toContain('1 个直接关联对象 · 2 条源连接')
  fireEvent.click(screen.getByRole('button',{name:'Next terminal'}))
  expect(worker.postMessage).toHaveBeenCalledWith(expect.objectContaining({type:'locate',id:'next'}))
})
