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
  expect(document.querySelectorAll('svg')).toHaveLength(0)
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
