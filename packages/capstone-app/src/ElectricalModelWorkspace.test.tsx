import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ElectricalModelWorkspace from './ElectricalModelWorkspace'
import type {HttpThreadTransport} from './threadHttpTransport'
import {ELECTRICAL_STREAMS,type ElectricalViewReady} from './electricalModelView'
import {electricalOverviewManifest,electricalOverviewRecords,electricalPage} from './electricalModelFixtures'
import type {ElectricalDownloadProgress} from './electricalViewDownload'
import type {LargeNetworkViewProps} from './LargeNetworkView'
const background=vi.hoisted(()=>({created:[] as {start:ReturnType<typeof vi.fn>;pause:ReturnType<typeof vi.fn>;dispose:ReturnType<typeof vi.fn>;publish:(value:ElectricalDownloadProgress)=>void}[]}))
afterEach(()=>{cleanup();sessionStorage.clear();background.created=[];vi.clearAllMocks()})
vi.mock('./electricalViewDownload',()=>({createElectricalViewDownload:(_manifest:unknown,_read:unknown,publish:(value:ElectricalDownloadProgress)=>void)=>{
  const download={start:vi.fn(),pause:vi.fn(),dispose:vi.fn(),publish};background.created.push(download);return download
}}))
vi.mock('./LargeNetworkView',()=>({LargeNetworkView:({scene,onActivate,canActivate}:LargeNetworkViewProps)=> <div>接线画布
  {[...scene.nodes.map(node=>({...node,type:'node' as const})),...scene.edges.map(edge=>({...edge,type:'edge' as const}))].filter(item=>canActivate?.(item)).map(item=><button key={item.id} onClick={()=>onActivate?.(item)}>展开 {item.label}</button>)}
</div>}))
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
  sessionStorage.setItem('restore',JSON.stringify({name:'站甲',request:{...identity,view_ref:'child',parent_view_ref:'root',schema:'capstone-electrical-view-request/1',source_id:'data-gateway',representation:'source_node_breaker',target:'station-object',artifact_ref:null}}))
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
it('keeps manual station navigation on remount but applies a new instruction request',async()=>{
  const request={...identity,schema:'capstone-electrical-view-request/1' as const,source_id:'data-gateway' as const,representation:'source_node_breaker' as const,target:null,artifact_ref:null}
  sessionStorage.setItem('manual',JSON.stringify({name:'站甲',request:{...request,target:'station-object',view_ref:'child',parent_view_ref:'root'},appliedRequestIdentity:JSON.stringify([request,1])}))
  const open=vi.fn(async(q:Record<string,unknown>)=>({...ready,view_ref:q.target?'child':'root',target:q.target??null,streams:Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,{total_count:0}]))}))
  const read=vi.fn(async(q:{view_ref:string;stream:string})=>({...identity,view_ref:q.view_ref,stream:q.stream,records:[],returned_count:0,total_count:0,next_cursor:null,complete:true}))
  const transport={electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport
  const ui=render(<ElectricalModelWorkspace storageKey="manual" transport={transport} requestedView={request} requestNonce={1}/>)
  await screen.findByText('接线画布')
  expect(open.mock.calls[0][0]).toMatchObject({parent_view_ref:'root',target:'station-object'})
  ui.rerender(<ElectricalModelWorkspace storageKey="manual" transport={transport} requestedView={request} requestNonce={2}/>)
  await waitFor(()=>expect(open.mock.calls.at(-1)?.[0]).not.toHaveProperty('target'))
})

it('merges published provincial models, renders complete overview before independent background details, and never restarts on rerender',async()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
  const open=vi.fn(async(_query:Record<string,unknown>)=>manifest),read=vi.fn(async request=>electricalPage(manifest,records,request))
  const transport={electricalModels:async()=>({scopes:[{model_ref:'scope:old',name:'旧目录'}],electrical_views:{source_grid_models:[{
    model_ref:manifest.model_ref,open_arguments:{model_ref:manifest.model_ref,selection_profile:'station'}}],v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport
  const ui=render(<ElectricalModelWorkspace transport={transport}/>)
  await screen.findByRole('option',{name:'旧目录'});await screen.findByRole('option',{name:manifest.model_ref})
  fireEvent.change(screen.getByRole('combobox'),{target:{value:manifest.model_ref}})
  await screen.findByText('接线画布')
  expect(open.mock.calls[0][0]).toMatchObject({model_ref:manifest.model_ref,selection_profile:'station',view_schema:'gateway-electrical-view/2'})
  expect(read.mock.calls.map(([request])=>request.stream)).toEqual(['summary_nodes','summary_edges'])
  expect(background.created).toHaveLength(1);expect(background.created[0].start).toHaveBeenCalledTimes(1)
  ui.rerender(<ElectricalModelWorkspace transport={transport}/>);expect(background.created).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'暂停后台下载'}));expect(background.created[0].pause).toHaveBeenCalled()
  expect(screen.getByText('接线画布')).toBeTruthy()
})

it('uses actual grid/station/edge targets, pauses background for foreground, and restores exact breadcrumb parents',async()=>{
  const records=electricalOverviewRecords(),root=electricalOverviewManifest(records)
  const child:ElectricalViewReady={...root,view_ref:'view:station-child',target:'target:station',streams:Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,{total_count:0}])) as ElectricalViewReady['streams']}
  const grid={...root,view_ref:'view:grid-child',target:'target:grid'}
  const open=vi.fn(async(q:Record<string,unknown>)=>q.target==='target:grid'?grid:q.target?{...child,target:q.target}:root)
  const read=vi.fn(async request=>electricalPage(request.view_ref===root.view_ref?root:request.view_ref===grid.view_ref?grid:child,
    request.view_ref===child.view_ref?{...records,...Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,[]]))}:records,request))
  const transport={electricalModels:async()=>({scopes:[{model_ref:root.model_ref,name:'省网'}],electrical_views:{v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport
  const ui=render(<ElectricalModelWorkspace storageKey="v2-navigation" transport={transport}/>)
  await screen.findByRole('option',{name:'省网'});fireEvent.change(screen.getByRole('combobox'),{target:{value:root.model_ref}})
  fireEvent.click(await screen.findByRole('button',{name:'展开 Region A'}))
  await waitFor(()=>expect(open.mock.calls.at(-1)?.[0]).toMatchObject({parent_view_ref:root.view_ref,target:'target:grid'}))
  await waitFor(()=>expect(screen.getByRole('navigation').textContent).toContain('Region A'))
  fireEvent.click(await screen.findByRole('button',{name:'展开 Station A'}))
  await waitFor(()=>expect(open.mock.calls.at(-1)?.[0]).toMatchObject({parent_view_ref:grid.view_ref,target:'target:station'}))
  await screen.findByText('0 个设备 · 0 个端口 · 0 条源连接')
  expect(open.mock.calls.at(-1)?.[0]).not.toHaveProperty('view_schema')
  expect(background.created).toHaveLength(1);expect(background.created[0].pause).toHaveBeenCalled()
  const starts=background.created[0].start.mock.calls.length
  expect(starts).toBeGreaterThan(1)
  ui.unmount();expect(background.created[0].dispose).toHaveBeenCalled()
  render(<ElectricalModelWorkspace storageKey="v2-navigation" transport={transport}/>)
  await screen.findByText('0 个设备 · 0 个端口 · 0 条源连接')
  expect(open.mock.calls.at(-1)?.[0]).toMatchObject({parent_view_ref:grid.view_ref,target:'target:station'})
  expect(screen.getByRole('navigation').textContent).toContain('省网Region AStation A')
  expect(screen.getByText('后台明细尚未恢复；返回根概览后继续下载。')).toBeTruthy()
})

it('preserves a user pause through edge closure navigation, disposes on model switch, and ignores old progress',async()=>{
  const records=electricalOverviewRecords(),root=electricalOverviewManifest(records),second={...root,model_ref:'other:model',view_ref:'other:view'}
  const child:ElectricalViewReady={...root,target:'target:line-set:one',view_ref:'line:view',streams:Object.fromEntries(ELECTRICAL_STREAMS.map(s=>[s,{total_count:0}])) as ElectricalViewReady['streams']}
  const open=vi.fn(async(q:Record<string,unknown>)=>q.model_ref===second.model_ref?second:q.target?child:root)
  const empty={...records,...Object.fromEntries(ELECTRICAL_STREAMS.map(stream=>[stream,[]]))}
  const read=vi.fn(async request=>electricalPage(request.view_ref===root.view_ref?root:request.view_ref===second.view_ref?second:child,request.view_ref===child.view_ref?empty:records,request))
  const transport={electricalModels:async()=>({scopes:[{model_ref:root.model_ref,name:'当前模型'},{model_ref:second.model_ref,name:'另一模型'}],electrical_views:{v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),electricalOpen:open,electricalRead:read} as unknown as HttpThreadTransport
  render(<ElectricalModelWorkspace transport={transport}/>)
  await screen.findByRole('option',{name:'当前模型'});fireEvent.change(screen.getByRole('combobox'),{target:{value:root.model_ref}})
  await screen.findByText('接线画布');const original=background.created[0]
  act(()=>original.publish({state:'running',loaded:1,total:5,streams:{}}))
  fireEvent.click(screen.getByRole('button',{name:'暂停后台下载'}));const starts=original.start.mock.calls.length
  fireEvent.click(screen.getByRole('button',{name:'展开 2 条源线路'}))
  await screen.findByText('0 个设备 · 0 个端口 · 0 条源连接')
  expect(open.mock.calls.at(-1)?.[0]).toMatchObject({target:'target:line-set:one',parent_view_ref:root.view_ref})
  expect(original.start).toHaveBeenCalledTimes(starts)
  fireEvent.click(screen.getByRole('button',{name:'继续后台下载'}));expect(original.start).toHaveBeenCalledTimes(starts+1)
  fireEvent.change(screen.getByRole('combobox'),{target:{value:second.model_ref}})
  expect(original.dispose).toHaveBeenCalledTimes(1)
  await screen.findByText('当前层概览完整',{exact:false});await waitFor(()=>expect(background.created).toHaveLength(2))
  act(()=>original.publish({state:'error',loaded:9,total:9,streams:{},error:'obsolete'}))
  expect(screen.queryByText(/obsolete/)).toBeNull()
})

it('retains overview after background failure and requires explicit resume even after independent navigation',async()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
  const child={...manifest,view_ref:'grid-child',target:'target:grid'}
  const transport={electricalModels:async()=>({scopes:[{model_ref:manifest.model_ref,name:'模型'}],electrical_views:{v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),
    electricalOpen:async(q:Record<string,unknown>)=>q.target?child:manifest,
    electricalRead:async(request:Parameters<typeof electricalPage>[2])=>electricalPage(request.view_ref===manifest.view_ref?manifest:child,records,request)} as unknown as HttpThreadTransport
  render(<ElectricalModelWorkspace transport={transport}/>)
  await screen.findByRole('option',{name:'模型'});fireEvent.change(screen.getByRole('combobox'),{target:{value:manifest.model_ref}})
  await screen.findByText('接线画布');const original=background.created[0],starts=original.start.mock.calls.length
  act(()=>original.publish({state:'error',loaded:1,total:5,streams:{},error:'cache_quota_exceeded'}))
  expect(screen.getByText('接线画布')).toBeTruthy();expect(screen.getByRole('button',{name:'继续后台下载'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'展开 Region A'}))
  await waitFor(()=>expect(screen.getByRole('navigation').textContent).toContain('Region A'))
  await screen.findByText('当前层概览完整',{exact:false})
  expect(original.start).toHaveBeenCalledTimes(starts)
})

it('rejects legacy child restoration without a parent instead of substituting its own view reference',async()=>{
  sessionStorage.setItem('old-child',JSON.stringify({request:{...identity,view_ref:'child',schema:'capstone-electrical-view-request/1',source_id:'data-gateway',representation:'source_node_breaker',target:'station-object',artifact_ref:null}}))
  const open=vi.fn()
  render(<ElectricalModelWorkspace storageKey="old-child" transport={{electricalModels:async()=>({scopes:[]}),electricalOpen:open} as unknown as HttpThreadTransport}/>)
  await screen.findByRole('alert');expect(open).not.toHaveBeenCalled()
})

it('aborts a stale foreground overview on model switch and ignores its eventual result',async()=>{
  const records=electricalOverviewRecords(),root=electricalOverviewManifest(records),other={...root,model_ref:'other:model',view_ref:'other:view'}
  let release:()=>void=()=>{},oldSignal:AbortSignal|undefined
  const read=vi.fn(async(request:Parameters<typeof electricalPage>[2],signal?:AbortSignal)=>{
    if(request.view_ref===root.view_ref){oldSignal=signal;await new Promise<void>(resolve=>{release=resolve})}
    return electricalPage(request.view_ref===root.view_ref?root:other,records,request)
  })
  const transport={electricalModels:async()=>({scopes:[{model_ref:root.model_ref,name:'模型甲'},{model_ref:other.model_ref,name:'模型乙'}],electrical_views:{v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),
    electricalOpen:async(q:Record<string,unknown>)=>q.model_ref===root.model_ref?root:other,electricalRead:read} as unknown as HttpThreadTransport
  render(<ElectricalModelWorkspace transport={transport}/>)
  await screen.findByRole('option',{name:'模型甲'});fireEvent.change(screen.getByRole('combobox'),{target:{value:root.model_ref}})
  await waitFor(()=>expect(oldSignal).toBeDefined())
  fireEvent.change(screen.getByRole('combobox'),{target:{value:other.model_ref}})
  await screen.findByText('接线画布');expect(oldSignal!.aborted).toBe(true)
  await act(async()=>{release();await Promise.resolve()})
  expect(background.created).toHaveLength(1)
  expect(screen.getByRole('navigation').textContent).toBe('模型乙')
})

it('retains published root schema/selection metadata across exact refresh restoration',async()=>{
  const records=electricalOverviewRecords(),manifest={...electricalOverviewManifest(records),overview_coverage:{source_selection:{profile:'station',boundary_policy:'retain_external_stub'}}}
  const open=vi.fn(async(_query:Record<string,unknown>)=>manifest)
  const transport={electricalModels:async()=>({scopes:[{model_ref:manifest.model_ref,name:'有名称的省网'}],electrical_views:{source_grid_models:[{
    model_ref:manifest.model_ref,open_arguments:{model_ref:manifest.model_ref,selection_profile:'station'}}],v2:{open_arguments:{view_schema:'gateway-electrical-view/2'}}}}),
    electricalOpen:open,electricalRead:async(request:Parameters<typeof electricalPage>[2])=>electricalPage(manifest,records,request)} as unknown as HttpThreadTransport
  const ui=render(<ElectricalModelWorkspace storageKey="metadata" transport={transport}/>)
  await screen.findByRole('option',{name:'有名称的省网'});expect(screen.getAllByRole('option')).toHaveLength(2)
  fireEvent.change(screen.getByRole('combobox'),{target:{value:manifest.model_ref}});await screen.findByText('接线画布')
  ui.unmount();render(<ElectricalModelWorkspace storageKey="metadata" transport={transport}/>)
  await screen.findByText('接线画布')
  expect(open.mock.calls.at(-1)?.[0]).toMatchObject({model_ref:manifest.model_ref,view_schema:'gateway-electrical-view/2',
    expected_model_revision:manifest.model_revision,selection_ref:manifest.selection_ref,selection_profile:'station',boundary_policy:'retain_external_stub'})
})
