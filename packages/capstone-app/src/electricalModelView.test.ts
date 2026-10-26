import {describe,it,expect,vi} from 'vitest'
import {ELECTRICAL_STREAMS,loadElectricalModelView,parseElectricalViewOpen,parseElectricalViewPage,parseElectricalViewFailure} from './electricalModelView'
import {electricalRecords,electricalManifest,electricalPage} from './electricalModelFixtures'

describe('frozen electrical record loading',()=>{
  it('reads only root groups, without downloading full devices or connections',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records,null);manifest.streams.devices.total_count=1000000
    const read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'groups'})
    expect(read).toHaveBeenCalledTimes(1);expect(read.mock.calls[0][0].stream).toBe('groups')
    expect(view.loadedStreams).toEqual(['groups']);expect(view.records.devices).toEqual([])
    await expect(loadElectricalModelView(manifest,read,{mode:'closure'})).rejects.toThrow('root_closure_requires_explicit_target')
    expect(read).toHaveBeenCalledTimes(1)
  })
  it('paginates all eight streams independently and retains typed identity and uncertainty',async()=>{
    const records=electricalRecords(),manifest=electricalManifest(records),read=vi.fn(async request=>electricalPage(manifest,records,request))
    const view=await loadElectricalModelView(manifest,read,{mode:'closure',pageSize:1})
    expect(view.records).toEqual(records);expect(view.loadedStreams).toEqual(ELECTRICAL_STREAMS)
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
