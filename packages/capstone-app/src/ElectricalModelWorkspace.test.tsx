import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ElectricalModelWorkspace from './ElectricalModelWorkspace'
import type {HttpThreadTransport} from './threadHttpTransport'
import {ELECTRICAL_STREAMS} from './electricalModelView'
afterEach(()=>{cleanup();sessionStorage.clear()})
vi.mock('./LargeNetworkView',()=>({LargeNetworkView:()=> <div>接线画布</div>}))
const identity={schema:'gateway-electrical-view/1',model_ref:'registered:any',model_revision:'r1',selection_ref:'s1',source_snapshot_ref:'source1',view_ref:'root'}
const ready={...identity,state:'ready',representation:'source_node_breaker',target:null,capture:{source_transaction_consistency_verified:false},streams:Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,{total_count:s==='groups'?1:0}]))}
const group={id:'station-object',kind:'station',name:'站甲',member_count:4,expand_target:'station-object'}
it('discovers without implicit selection and reads only a bounded directory page before explicit station expansion',async()=>{
  const open=vi.fn(async(q:Record<string,unknown>)=>q.target?{...ready,target:q.target,view_ref:'child',streams:Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,{total_count:0}]))}:ready)
  const read=vi.fn(async(q:{view_ref:string;stream:string})=>({...identity,view_ref:q.view_ref,stream:q.stream,records:q.view_ref==='root'?[group]:[],returned_count:q.view_ref==='root'?1:0,total_count:q.view_ref==='root'?1:0,next_cursor:null,complete:true}))
  const transport={electricalModels:async()=>({scopes:[{model_ref:'registered:any',name:'登记模型'}]}),electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport
  render(<ElectricalModelWorkspace transport={transport}/>)
  await screen.findByRole('option',{name:'登记模型'})
  expect(open).not.toHaveBeenCalled()
  fireEvent.change(await screen.findByRole('combobox',{name:'电网模型'}),{target:{value:'registered:any'}})
  fireEvent.click(await screen.findByRole('button',{name:'站甲 · 4 个设备'}))
  await screen.findByText('接线画布')
  expect(open.mock.calls[1][0]).toMatchObject({model_ref:'registered:any',parent_view_ref:'root',expected_model_revision:'r1',target:'station-object'})
  expect(read.mock.calls[0][0]).toMatchObject({view_ref:'root',stream:'groups',limit:200})
  expect(read.mock.calls.filter(([q])=>q.view_ref==='root')).toHaveLength(1)
})
it('reports repeated page records without throwing during render',async()=>{
  const manifest={...ready,streams:{...ready.streams,groups:{total_count:2}}}
  const read=vi.fn(async(q:{cursor?:string})=>({...identity,stream:'groups',records:[group],returned_count:1,total_count:2,next_cursor:q.cursor?null:'next',complete:!!q.cursor}))
  render(<ElectricalModelWorkspace transport={{electricalModels:async()=>({scopes:[{model_ref:'registered:any',name:'登记模型'}]}),electricalOpen:async()=>manifest,electricalRead:read} as unknown as HttpThreadTransport}/>)
  await screen.findByRole('option',{name:'登记模型'})
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'registered:any'}})
  fireEvent.click(await screen.findByRole('button',{name:'加载更多站点'}))
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toMatch(/重复/))
  expect(screen.getAllByRole('button',{name:'站甲 · 4 个设备'})).toHaveLength(1)
})
it('restores a saved view only through an exact frozen reopen',async()=>{
  sessionStorage.setItem('restore',JSON.stringify({name:'站甲',request:{...identity,schema:'capstone-electrical-view-request/1',source_id:'data-gateway',representation:'source_node_breaker',target:'station-object',artifact_ref:null}}))
  const open=vi.fn(async()=>({...ready,target:'station-object',model_revision:'changed'})),read=vi.fn()
  render(<ElectricalModelWorkspace storageKey="restore" transport={{electricalModels:async()=>({scopes:[]}),electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport}/>)
  await screen.findByRole('alert')
  expect(open.mock.calls[0]).toBeDefined()
  expect(read).not.toHaveBeenCalled()
})
it('does not accept a reopened descriptor with a different frozen revision',async()=>{
  const read=vi.fn()
  render(<ElectricalModelWorkspace transport={{electricalOpen:async()=>({...ready,model_revision:'other'}),electricalRead:read} as unknown as HttpThreadTransport}
    requestedView={{schema:'capstone-electrical-view-request/1',source_id:'data-gateway',...Object.fromEntries(['model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref'].map(k=>[k,identity[k as keyof typeof identity]])),representation:'source_node_breaker',target:null,artifact_ref:null} as never}/>)
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toMatch(/版本|来源/))
  expect(read).not.toHaveBeenCalled()
})
