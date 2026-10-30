import {describe,it,expect,vi} from 'vitest'
import {ELECTRICAL_DETAIL_STREAMS,ELECTRICAL_SUMMARY_STREAMS,loadElectricalModelView,parseElectricalViewOpen,parseElectricalViewPage,parseElectricalViewFailure} from './electricalModelView'
import {electricalRecords,electricalManifest,electricalPage,electricalOverviewRecords,electricalOverviewManifest} from './electricalModelFixtures'

describe('frozen electrical record loading',()=>{
  it.each([201,1000])('accepts %s validated records when the returned action uses its own page size',async size=>{
    const records=electricalRecords()
    records.groups=Array.from({length:size+1},(_,index)=>({...records.groups[0],id:`group-${index}`}))
    const manifest=electricalManifest(records,null)
    const read=vi.fn(async request=>electricalPage(manifest,records,{...request,limit:size}))
    const view=await loadElectricalModelView(manifest,read,{mode:'groups',pageSize:200})
    expect(view.records.groups).toEqual(records.groups)
    expect(read).toHaveBeenCalledTimes(2)
    expect(read.mock.calls[0][0].limit).toBe(200)
    expect(read.mock.calls[1][0].cursor).toBe(`cursor:groups:${size}`)
  })
  it.each(['over_bound','wrong_count'])('rejects %s pages even when the gateway action controls page size',async kind=>{
    const records=electricalRecords(),size=kind==='over_bound'?1001:201
    records.groups=Array.from({length:size},(_,index)=>({...records.groups[0],id:`group-${index}`}))
    const manifest=electricalManifest(records,null)
    await expect(loadElectricalModelView(manifest,async request=>{
      const page=electricalPage(manifest,records,{...request,limit:size})
      return kind==='wrong_count'?{...page,returned_count:size-1}:page
    },{mode:'groups',pageSize:200})).rejects.toThrow('invalid_page_counts')
  })
  it('reads only root groups, without downloading full devices or connections',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records,null);manifest.streams.devices.total_count=1000000
    const read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'groups'})
    expect(read).toHaveBeenCalledTimes(1);expect(read.mock.calls[0][0].stream).toBe('groups')
    expect(view.loadedStreams).toEqual(['groups']);expect(view.records.devices).toEqual([])
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('root_closure_requires_explicit_target')
    expect(read).toHaveBeenCalledTimes(1)
  })
  it('allows calculation root closure only with an explicit ready artifact and exact native bus alias',async()=>{
    const records=electricalRecords();records.devices.push({id:'j1',kind:'bus',name:'Native bus',element_key:7});records.connectivity_nodes[0].kind='calculation_bus'
    const manifest=electricalManifest(records,null);manifest.representation='calculation_bus_branch'
    const read=vi.fn(async request=>electricalPage(manifest,records,request))
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('calculation_artifact_required');expect(read).not.toHaveBeenCalled()
    manifest.artifact_ref='artifact:one'
    expect((await loadElectricalModelView(manifest,read,{mode:'closure'})).records.devices).toHaveLength(2)
    records.devices[1].kind='load'
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('ambiguous_object_identity')
    records.devices[1].kind='bus';manifest.representation='source_node_breaker';manifest.target='station'
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('ambiguous_object_identity')
  })
  it('paginates all eight streams independently and retains typed identity and uncertainty',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records),read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'closure',pageSize:1})
    expect(view.records).toEqual(records);expect(view.loadedStreams).toEqual(ELECTRICAL_DETAIL_STREAMS)
    for(const [request] of read.mock.calls)if(request.cursor)expect(request.cursor).toContain(`:${request.stream}:`)
    expect(view.records.ports[0].role).toBeNull();expect(view.records.devices[0].element_key).toBe(7)
    expect(view.manifest.capture.source_transaction_consistency_verified).toBe(false)
  })
  it.each(['model_ref','model_revision','view_ref','source_snapshot_ref','selection_ref'])('rejects a changed frozen %s before exposing data',async field=>{
    const records=electricalRecords(),manifest=electricalManifest(records)
    await expect(loadElectricalModelView(manifest,async request=>({...electricalPage(manifest,records,request),[field]:'changed'}),{mode:'closure'})).rejects.toThrow('frozen_baseline_mismatch')
  })
  it('rejects duplicates across pages and repeated cursors',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records)
    await expect(loadElectricalModelView(manifest,async request=>{const page=electricalPage(manifest,records,request);return request.stream==='ports'&&request.cursor?{...page,records:[records.ports[0]]}:page},{mode:'closure',pageSize:1})).rejects.toThrow('duplicate_record')
    let calls=0
    await expect(loadElectricalModelView({...manifest,streams:{...manifest.streams,groups:{total_count:3}}},async request=>({...electricalPage(manifest,records,request),records:[{...records.groups[0],id:`g${++calls}`}],returned_count:1,total_count:3,next_cursor:'repeated',complete:false}),{mode:'groups'})).rejects.toThrow('cursor_cycle')
  })
  it.each(['total','truncated','empty'])('rejects %s stream progress inconsistencies',async kind=>{
    const records=electricalRecords(),manifest=electricalManifest(records)
    await expect(loadElectricalModelView(manifest,async request=>{const page=electricalPage(manifest,records,request);return kind==='total'?{...page,total_count:99}:kind==='truncated'?{...page,records:[],returned_count:0}: {...page,records:[],returned_count:0,next_cursor:'no-progress',complete:false}},{mode:'groups'})).rejects.toThrow(kind==='total'?'stream_manifest_mismatch':'incomplete_stream')
  })
  it('checks both pre-abort and cancellation while a page is in flight',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records),controller=new AbortController(),read=vi.fn(async()=>({}))
    controller.abort();await expect(loadElectricalModelView(manifest,read,{mode:'groups',signal:controller.signal})).rejects.toMatchObject({name:'AbortError'});expect(read).not.toHaveBeenCalled()
    const active=new AbortController(),delayed=vi.fn(async()=>{active.abort();return {malformed:true}})
    await expect(loadElectricalModelView(manifest,delayed,{mode:'closure',signal:active.signal})).rejects.toMatchObject({name:'AbortError'});expect(delayed).toHaveBeenCalledTimes(1)
  })
  it('enforces display budgets before reads and rejects missing reference closure',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records),read=vi.fn(async request=>electricalPage(manifest,records,request))
    await expect(loadElectricalModelView(manifest,read,{mode:'closure',maxRecords:1})).rejects.toThrow('view_budget_exceeded');expect(read).not.toHaveBeenCalled()
    await expect(loadElectricalModelView(manifest,read,{mode:'closure',maxPages:1})).rejects.toThrow('page_budget_exceeded')
    records.ports[0].device_id='missing'
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('missing_port_device')
  })
  it.each(['connection','relation','boundary'])('rejects a missing or inconsistent %s reference without fabricating records',async kind=>{
    const records=electricalRecords()
    if(kind==='connection')records.connections[0].connectivity_node_id='absent'
    if(kind==='relation')records.device_relations.push({id:'r',parent_id:'device',child_id:'absent',child_stream:'ports',kind:'membership',electrical_connection:false})
    if(kind==='boundary')records.boundaries[0].device_id='absent'
    const manifest=electricalManifest(records)
    await expect(loadElectricalModelView(manifest,async request=>electricalPage(manifest,records,request),{mode:'closure'})).rejects.toThrow(kind==='connection'?'missing_connection_endpoint':kind==='relation'?'missing_relation_endpoint':'invalid_boundary_endpoint')
  })
  it('parses preparing and unsupported separately, without treating structure as numerical readiness',()=>{
    expect(parseElectricalViewOpen({schema:'gateway-electrical-view/1',state:'preparing',model_ref:'model',preparation_ref:'job'})).toMatchObject({state:'preparing'})
    expect(parseElectricalViewFailure({detail:{code:'unsupported_representation',retryable:false,recovery_action:'select_supported_representation'}})).toMatchObject({state:'unsupported',retryable:false})
    expect(()=>parseElectricalViewOpen({schema:'gateway-electrical-view/1',state:'unsupported'})).toThrow('invalid_state')
    expect(parseElectricalViewOpen(electricalManifest())).toMatchObject({state:'ready',readiness:'partial'})
  })
  it('rejects invented conducting membership and malformed page records',()=>{
    const records=electricalRecords(),manifest=electricalManifest(records)
    const page=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'device_relations'})
    expect(()=>parseElectricalViewPage({...page,records:[{id:'r',parent_id:'device',child_id:'p1',child_stream:'ports',kind:'membership',electrical_connection:true}],returned_count:1,total_count:1})).toThrow('invalid_membership')
    const ports=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'ports'})
    expect(()=>parseElectricalViewPage({...ports,records:[...ports.records,...ports.records],returned_count:4,total_count:4})).toThrow('duplicate_record')
  })
})

describe('v2 summary loading',()=>{
  it('reads both overview streams to completion without reading detail streams',async()=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
    manifest.streams.devices.total_count=1000000
    const read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'overview',pageSize:1})
    expect(view.loadedStreams).toEqual(ELECTRICAL_SUMMARY_STREAMS)
    expect(view.records.summary_nodes).toEqual(records.summary_nodes)
    expect(view.records.summary_edges).toEqual(records.summary_edges)
    expect(view.records.devices).toEqual([])
    expect(read.mock.calls.map(([request])=>request.stream)).toEqual(['summary_nodes','summary_nodes','summary_nodes','summary_edges','summary_edges'])
    expect(view.records.summary_nodes[0].source_ref).toEqual(records.summary_nodes[0].source_ref)
  })
  it('loads v2 closures from eight detail streams even when summaries exceed the display budget',async()=>{
    const records=electricalRecords(),manifest=electricalOverviewManifest(records);manifest.target='station'
    manifest.streams.summary_nodes!.total_count=1000000
    const read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'closure'})
    expect(view.loadedStreams).toEqual(ELECTRICAL_DETAIL_STREAMS)
    expect(read.mock.calls.map(([request])=>request.stream)).toEqual(ELECTRICAL_DETAIL_STREAMS)
    expect(view.records.summary_nodes).toEqual([])
  })
  it('requires published v2 summary streams and keeps v1 summary reads invalid',async()=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
    const missing={...manifest,streams:{...manifest.streams}};delete missing.streams.summary_edges
    expect(()=>parseElectricalViewOpen(missing)).toThrow('invalid_stream_total')
    expect(()=>parseElectricalViewOpen({...manifest,representation:'calculation_bus_branch'})).toThrow('invalid_representation')
    const v1=electricalManifest(records)
    await expect(loadElectricalModelView(v1,vi.fn(),{mode:'overview'})).rejects.toThrow('overview_requires_v2')
    expect(()=>parseElectricalViewPage({...electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'summary_nodes'}),schema:'gateway-electrical-view/1'})).toThrow('invalid_stream')
  })
  it('rejects page schema drift even when every frozen identity matches',async()=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records);manifest.target='station'
    await expect(loadElectricalModelView(manifest,async request=>({...electricalPage(manifest,records,request),schema:'gateway-electrical-view/1'}),{mode:'closure'})).rejects.toThrow('frozen_baseline_mismatch')
  })
  it.each(['model_ref','model_revision','view_ref','source_snapshot_ref','selection_ref'])('rejects overview %s drift',async field=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
    await expect(loadElectricalModelView(manifest,async request=>({...electricalPage(manifest,records,request),[field]:'changed'}),{mode:'overview'})).rejects.toThrow('frozen_baseline_mismatch')
  })
  it.each(['duplicate','total','cursor','missing_endpoint'])('rejects invalid overview %s',async kind=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
    if(kind==='missing_endpoint')records.summary_edges[0].target_id='absent'
    await expect(loadElectricalModelView(manifest,async request=>{
      const page=electricalPage(manifest,records,request)
      if(kind==='duplicate'&&request.stream==='summary_nodes'&&request.cursor)return {...page,records:[records.summary_nodes[0]]}
      if(kind==='total')return {...page,total_count:99}
      if(kind==='cursor')return {...page,next_cursor:'cursor:summary_nodes:1',complete:false}
      return page
    },{mode:'overview',pageSize:1})).rejects.toThrow({duplicate:'duplicate_record',total:'stream_manifest_mismatch',cursor:'cursor_cycle',missing_endpoint:'missing_summary_endpoint'}[kind])
  })
  it.each(['node_equivalent','edge_equivalent','verified_connection','bad_count','missing_target'])('rejects invented summary semantics: %s',kind=>{
    const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records),stream=kind==='node_equivalent'?'summary_nodes':'summary_edges'
    const page=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream})
    const first={...page.records[0]}
    if(kind.endsWith('equivalent'))first.electrical_equivalent=true
    if(kind==='verified_connection')first.electrical_connectivity_verified=true
    if(kind==='bad_count')first.member_count=0
    if(kind==='missing_target')delete first.expand_target
    expect(()=>parseElectricalViewPage({...page,records:[first],returned_count:1})).toThrow(kind==='node_equivalent'?'invalid_summary_node':'invalid_summary_edge')
  })
})
