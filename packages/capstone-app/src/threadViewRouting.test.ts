import {expect,it} from 'vitest'
import {parseThreadSourceViewRequest,parseThreadDisplayRequest,selectThreadViewProposal} from './threadViewRouting'
import {sampleDiagramView} from './networkFixture'
import type {EventEnvelope,ModelContextSnapshot} from './threadProtocol'
import type {ThreadNetworkTask} from './threadProjectionStore'

const request={schema:'capstone-grid-source-view-request/1',source_id:'data-gateway',scope_id:'north',scope_name:'华北',level:null,selected_object_id:null,view_ref:'verified-view',source_snapshot:{metadata_snapshot:'snapshot',source_instance:'gateway-instance'},voltage_min_kv:330,display_grouping_only:false}
const event=(seq:number,payload:Record<string,unknown>={source_view:request},attemptId='latest'):EventEnvelope=>({eventId:`event${seq}`,eventSeq:seq,eventType:'runtime_event',eventVersion:1,threadId:'thread',runId:'run',attemptId,visibility:'public',occurredAt:'2026-10-26T00:00:00Z',payload})
const currentContext:ModelContextSnapshot={id:'context',modelId:sampleDiagramView.diagram.model.id,modelRevision:sampleDiagramView.diagram.model.revision,implementationFamily:'pandapower',selectionRevision:'selection',enabledProfiles:[]}
const model=(eventSeq:number,overrides:Partial<ThreadNetworkTask>={}):ThreadNetworkTask=>({attemptId:'latest',eventSeq,pageId:'page',context:currentContext,view:sampleDiagramView,...overrides})
const electricalRequest={schema:'capstone-electrical-view-request/1',source_id:'data-gateway',model_ref:'grid:custom',model_revision:'revision',
  view_ref:'frozen',selection_ref:'selection',source_snapshot_ref:'snapshot',representation:'source_node_breaker',target:null,artifact_ref:null}

it('preserves exact optional schema and root selection metadata on verified electrical requests',()=>{
  const root={...electricalRequest,view_schema:'gateway-electrical-view/2',selection_profile:'province_all_ac',boundary_policy:'retain_external_stub'}
  expect(parseThreadDisplayRequest(root)).toEqual(root)
  expect(parseThreadDisplayRequest({...root,boundary_policy:'internal_only',selection_profile:'a'.repeat(64)})).toBeTruthy()
  expect(parseThreadDisplayRequest({...electricalRequest,view_schema:'gateway-electrical-view/1'})).toBeTruthy()
  expect(parseThreadDisplayRequest(electricalRequest)).toEqual(electricalRequest)
  const proposal=selectThreadViewProposal({events:[event(1,{source_view:root})],networkTasks:[],attemptId:'latest',currentContext})
  expect(proposal?.kind==='source'&&proposal.request).toEqual(root)
})

it('retains frozen child schema and actual parent reference without root-only selection overrides',()=>{
  const child={...electricalRequest,view_schema:'gateway-electrical-view/2',target:'opaque:station',parent_view_ref:'actual:parent'}
  expect(parseThreadDisplayRequest(child)).toEqual(child)
  expect(parseThreadDisplayRequest({...child,parent_view_ref:'p'.repeat(2048)})).toBeTruthy()
  expect(parseThreadDisplayRequest({...electricalRequest,representation:'calculation_bus_branch',artifact_ref:'artifact',view_schema:'gateway-electrical-view/1'})).toBeTruthy()
})

it.each([
  {view_schema:'gateway-electrical-view/3'}, {view_schema:['gateway-electrical-view/2']}, {view_schema:null}, {view_schema:undefined},
  {view_schema:'gateway-electrical-view/2',representation:'calculation_bus_branch',artifact_ref:'artifact'},
  {selection_profile:''}, {selection_profile:'A_profile'}, {selection_profile:'a/b'}, {selection_profile:'a'.repeat(65)}, {selection_profile:'a\n'},
  {selection_profile:null}, {selection_profile:undefined}, {selection_profile:['province']},
  {boundary_policy:'drop_external'}, {boundary_policy:null}, {boundary_policy:undefined}, {boundary_policy:['internal_only']},
  {parent_view_ref:''}, {parent_view_ref:null}, {parent_view_ref:undefined},
  {parent_view_ref:'p'.repeat(2049),target:'station'}, {parent_view_ref:'bad\nparent',target:'station'},
  {parent_view_ref:'frozen',target:'station'}, {parent_view_ref:'parent'},
  {parent_view_ref:'parent',target:'station',selection_profile:'province'},
  {parent_view_ref:'parent',target:'station',boundary_policy:'internal_only'},
  {representation:'calculation_bus_branch',artifact_ref:'artifact',selection_profile:'province'},
  {representation:'calculation_bus_branch',artifact_ref:'artifact',boundary_policy:'retain_external_stub'},
  {arbitrary_metadata:'not-admitted'},
])('rejects invalid or incompatible optional electrical metadata %#',metadata=>{
  expect(parseThreadDisplayRequest({...electricalRequest,...metadata})).toBeNull()
})

it('applies the backend ASCII JSON budget to electrical descriptors with multibyte identities',()=>{
  const oversized={...electricalRequest,target:'站'.repeat(512)}
  for(const field of ['model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref'] as const)oversized[field]='网'.repeat(512)
  expect(parseThreadDisplayRequest(oversized)).toBeNull()
})

it('routes only current successful frozen electrical descriptors with full model identity',()=>{
  const request={schema:'capstone-electrical-view-request/1',source_id:'data-gateway',model_ref:'grid:custom',model_revision:'revision',
    view_ref:'frozen',selection_ref:'selection',source_snapshot_ref:'snapshot',representation:'source_node_breaker',target:null,artifact_ref:null}
  expect(parseThreadDisplayRequest(request)).toEqual(request)
  expect(parseThreadDisplayRequest({...request,model_revision:''})).toBeNull()
  expect(parseThreadDisplayRequest({...request,representation:'calculation_bus_branch'})).toBeNull()
  expect(parseThreadDisplayRequest({...request,url:'http://untrusted'})).toBeNull()
  const input={events:[event(1,{source_view:request})],networkTasks:[],attemptId:'latest',currentContext}
  expect(selectThreadViewProposal(input)?.kind).toBe('source')
  expect(selectThreadViewProposal({...input,attemptId:'other'})).toBeNull()
  expect(selectThreadViewProposal({...input,events:[event(1,{source_view:request,is_error:true})]})).toBeNull()
})

it('accepts only the complete bounded host descriptor and preserves immutable source identity',()=>{
  const parsed=parseThreadSourceViewRequest(request)
  expect(parsed).toEqual(request)
  expect(parsed).not.toBe(request)
  expect(parsed?.source_snapshot).not.toBe(request.source_snapshot)
  expect(parseThreadSourceViewRequest({...request,level:'station',selected_object_id:'station',display_grouping_only:true})).toBeTruthy()
  expect(parseThreadSourceViewRequest({...request,level:'region',display_grouping_only:true})).toBeTruthy()
})
it.each([
  {...request,schema:'other/1'}, {...request,source_id:'caller-endpoint'}, {...request,nodes:[]},
  {...request,scope_name:undefined}, {...request,scope_id:''}, {...request,view_ref:'v'.repeat(513)},
  {...request,source_snapshot:{...request.source_snapshot,credential:'no'}},
  {...request,source_snapshot:{metadata_snapshot:'snapshot'}},
  {...request,scope_name:'bad\nname'}, {...request,level:'corridor'},
  {...request,level:['region'],display_grouping_only:true},
  {...request,level:{toString:'region'},display_grouping_only:true},
  {...request,level:null,display_grouping_only:true}, {...request,level:'region',display_grouping_only:false},
  {...request,level:'equipment',selected_object_id:null,display_grouping_only:true},
  {...request,level:null,selected_object_id:'equipment'},
  {...request,voltage_min_kv:-1}, {...request,voltage_min_kv:Infinity}, {...request,voltage_min_kv:true},
])('rejects malformed, mismatched raw/grouped or unbounded descriptors %#',value=>{
  expect(parseThreadSourceViewRequest(value)).toBeNull()
})
it('selects the latest valid public hint from the exact latest Attempt regardless of input order',()=>{
  const latest=event(9,{source_view:{...request,view_ref:'latest-verified'}})
  const events=[latest,event(12,{source_view:request},'old'),{...event(15),visibility:'diagnostic' as const},event(16,{source_view:{...request,credential:'invalid'}}),event(2)]
  expect(selectThreadViewProposal({events,networkTasks:[],attemptId:'latest',currentContext})).toEqual({kind:'source',eventSeq:9,attemptId:'latest',request:{...request,view_ref:'latest-verified'}})
})
it.each([{is_error:true},{isError:true},{ok:false},{status:'error'},{status:'failed'},{phase:'aborted'},{error:{message:'failed'}},{is_error:'false'},{status:{toString:0}},{phase:['ok']}])('ignores a failed or malformed source event %#',flags=>{
  expect(selectThreadViewProposal({events:[event(1,{source_view:request,...flags})],networkTasks:[],attemptId:'latest',currentContext})).toBeNull()
})
it('does not route plain questions, table outputs, tool names, historical goals or raw network layers',()=>{
  const events=[event(1,{text:'Show the north grid source topology',tool_name:'get_network_topology_view'}),
    {...event(2,{source_view:request}),eventType:'assistant_delta'},
    {...event(3,{network_view:sampleDiagramView}),eventType:'network_layer'},
    event(4,{work:{goal:'old grid question'},answer:'Table only',source_view:request},'old')]
  expect(selectThreadViewProposal({events,networkTasks:[model(4,{attemptId:'old'})],attemptId:'latest',currentContext})).toBeNull()
  expect(selectThreadViewProposal({events:[event(1)],networkTasks:[model(2)],attemptId:null,currentContext})).toBeNull()
})
it('uses only an admitted actual model task view matching the complete current context identity',()=>{
  const task=model(5)
  const proposal=selectThreadViewProposal({events:[],networkTasks:[task],attemptId:'latest',currentContext})
  expect(proposal).toEqual({kind:'model',eventSeq:5,attemptId:'latest',contextId:'context',pageId:'page',view:sampleDiagramView})
  if(proposal?.kind==='model')expect(proposal.view).toBe(task.view)
  for(const key of ['id','modelId','modelRevision','implementationFamily','selectionRevision'] as const){
    expect(selectThreadViewProposal({events:[],networkTasks:[model(8,{context:{...currentContext,[key]:'wrong'}})],attemptId:'latest',currentContext})).toBeNull()
  }
  expect(selectThreadViewProposal({events:[],networkTasks:[task],attemptId:'latest',currentContext:null})).toBeNull()
})
it('follows actual source/model transitions and produces the same proposal on replay',()=>{
  const source=event(10),task=model(8)
  expect(selectThreadViewProposal({events:[source],networkTasks:[task],attemptId:'latest',currentContext})?.kind).toBe('source')
  const later=model(12)
  const first=selectThreadViewProposal({events:[source],networkTasks:[task,later],attemptId:'latest',currentContext})
  expect(first?.kind).toBe('model')
  expect(selectThreadViewProposal({events:[source],networkTasks:[later,task],attemptId:'latest',currentContext})).toEqual(first)
  expect(selectThreadViewProposal({events:[event(15)],networkTasks:[later],attemptId:'new-instruction',currentContext})).toBeNull()
})
it('never promotes a manual historical baseline to an automatic instruction view or ranks it above a source hint',()=>{
  const baseline=model(99,{presentationSource:'historical_baseline'})
  expect(selectThreadViewProposal({events:[],networkTasks:[baseline],attemptId:'latest',currentContext})).toBeNull()
  expect(selectThreadViewProposal({events:[event(10)],networkTasks:[baseline],attemptId:'latest',currentContext})?.kind).toBe('source')
})
