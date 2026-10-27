import type {GridSourceLevel} from './gridSource'
import type {DiagramNetworkView} from './types'
import type {EventEnvelope,ModelContextSnapshot} from './threadProtocol'
import type {ThreadNetworkTask} from './threadProjectionStore'

/** Host-verified presentation request; it grants neither a model nor calculation evidence. */
export type ThreadSourceViewRequest={
  schema:'capstone-grid-source-view-request/1';source_id:'data-gateway'
  scope_id:string;scope_name:string;level:GridSourceLevel;selected_object_id:string|null
  view_ref:string;source_snapshot:{metadata_snapshot:string;source_instance:string}
  voltage_min_kv:number|null;display_grouping_only:boolean
}
export type ThreadElectricalViewRequest={schema:'capstone-electrical-view-request/1';source_id:'data-gateway';
  model_ref:string;model_revision:string;view_ref:string;selection_ref:string;source_snapshot_ref:string;
  representation:'source_node_breaker'|'calculation_bus_branch';target:string|null;artifact_ref:string|null;
  /** Describes the frozen view; child open calls inherit schema from their parent. */
  view_schema?:'gateway-electrical-view/1'|'gateway-electrical-view/2';
  selection_profile?:string;boundary_policy?:'retain_external_stub'|'internal_only';parent_view_ref?:string}
export type ThreadDisplayRequest=ThreadSourceViewRequest|ThreadElectricalViewRequest
export type ThreadViewProposal=
  |{kind:'source';eventSeq:number;attemptId:string;request:ThreadDisplayRequest}
  |{kind:'model';eventSeq:number;attemptId:string;contextId:string;pageId:string;view:DiagramNetworkView}
const object=(value:unknown):value is Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)
const text=(value:unknown):value is string=>typeof value==='string'&&value.length<=512&&value.trim().length>0&&!/[\u0000-\u001f\u007f]/.test(value)
const keys=(value:Record<string,unknown>,expected:readonly string[])=>Object.keys(value).length===expected.length&&expected.every(key=>Object.hasOwn(value,key))
const sequence=(value:number)=>Number.isSafeInteger(value)&&value>0
const electricalFields=['schema','source_id','model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref','representation','target','artifact_ref'] as const
const electricalMetadata=['view_schema','selection_profile','boundary_policy','parent_view_ref'] as const
const allowedElectricalFields=new Set<string>([...electricalFields,...electricalMetadata])
function boundedElectricalDescriptor(value:Record<string,unknown>):boolean {
  // The backend budgets Python's ASCII JSON, including its separator spaces.
  // All admitted descriptor fields are scalar strings or null.
  const ascii=JSON.stringify(value).replace(/[\u007f-\uffff]/g,char=>`\\u${char.charCodeAt(0).toString(16).padStart(4,'0')}`)
  return ascii.length+Object.keys(value).length*2-1<=16*1024
}

export function parseThreadDisplayRequest(value:unknown):ThreadDisplayRequest|null {
  if(!object(value)||value.schema!=='capstone-electrical-view-request/1')return parseThreadSourceViewRequest(value)
  if(!electricalFields.every(key=>Object.hasOwn(value,key))||Object.keys(value).some(key=>!allowedElectricalFields.has(key))
    ||value.source_id!=='data-gateway'||value.representation!=='source_node_breaker'&&value.representation!=='calculation_bus_branch'
    ||!['model_ref','model_revision','view_ref','selection_ref','source_snapshot_ref'].every(key=>text(value[key]))
    ||!(value.target===null||text(value.target))||!(value.artifact_ref===null||text(value.artifact_ref))
    ||value.representation==='calculation_bus_branch'&&!text(value.artifact_ref))return null
  if(Object.hasOwn(value,'view_schema')&&(value.view_schema!=='gateway-electrical-view/1'&&value.view_schema!=='gateway-electrical-view/2'
    ||value.view_schema==='gateway-electrical-view/2'&&value.representation!=='source_node_breaker'))return null
  if(Object.hasOwn(value,'selection_profile')&&(typeof value.selection_profile!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(value.selection_profile)))return null
  if(Object.hasOwn(value,'boundary_policy')&&value.boundary_policy!=='retain_external_stub'&&value.boundary_policy!=='internal_only')return null
  if(Object.hasOwn(value,'parent_view_ref')&&(typeof value.parent_view_ref!=='string'||!value.parent_view_ref.length||value.parent_view_ref.length>2048
    ||/[\u0000-\u001f]/.test(value.parent_view_ref)||value.parent_view_ref===value.view_ref||!value.target
    ||Object.hasOwn(value,'selection_profile')||Object.hasOwn(value,'boundary_policy')))return null
  if(value.representation==='calculation_bus_branch'&&(Object.hasOwn(value,'selection_profile')||Object.hasOwn(value,'boundary_policy')))return null
  if(!boundedElectricalDescriptor(value))return null
  return {...value} as ThreadElectricalViewRequest
}

export function parseThreadSourceViewRequest(value:unknown):ThreadSourceViewRequest|null{
  if(!object(value)||!keys(value,['schema','source_id','scope_id','scope_name','level','selected_object_id','view_ref','source_snapshot','voltage_min_kv','display_grouping_only'])||
    value.schema!=='capstone-grid-source-view-request/1'||value.source_id!=='data-gateway'||
    !text(value.scope_id)||!text(value.scope_name)||!text(value.view_ref)||
    !(value.level===null||typeof value.level==='string'&&['region','station','equipment'].includes(value.level))||
    !(value.selected_object_id===null||text(value.selected_object_id))||
    typeof value.display_grouping_only!=='boolean'||value.display_grouping_only!==(value.level!==null))return null
  if(value.level===null&&value.selected_object_id!==null||(value.level==='station'||value.level==='equipment')&&value.selected_object_id===null)return null
  if(value.voltage_min_kv!==null&&(typeof value.voltage_min_kv!=='number'||!Number.isFinite(value.voltage_min_kv)||value.voltage_min_kv<0))return null
  const snapshot=value.source_snapshot
  if(!object(snapshot)||!keys(snapshot,['metadata_snapshot','source_instance'])||!text(snapshot.metadata_snapshot)||!text(snapshot.source_instance))return null
  return {schema:'capstone-grid-source-view-request/1',source_id:'data-gateway',scope_id:value.scope_id,scope_name:value.scope_name,
    level:value.level as GridSourceLevel,selected_object_id:value.selected_object_id as string|null,view_ref:value.view_ref,
    source_snapshot:{metadata_snapshot:snapshot.metadata_snapshot,source_instance:snapshot.source_instance},
    voltage_min_kv:value.voltage_min_kv as number|null,display_grouping_only:value.display_grouping_only}
}
function successful(payload:Record<string,unknown>):boolean{
  for(const key of ['ok','is_error','isError'])if(payload[key]!==undefined&&typeof payload[key]!=='boolean')return false
  if(payload.ok===false||payload.is_error===true||payload.isError===true)return false
  const failed=new Set(['error','failed','failure','aborted','cancelled','interrupted'])
  for(const key of ['status','phase']){
    const value=payload[key]
    if(value===undefined)continue
    if(typeof value==='string'){if(failed.has(value))return false}
    else if(typeof value==='number'){if(!Number.isFinite(value)||value>=400)return false}
    else return false
  }
  for(const value of [payload.error,payload.failure])if(value!==undefined&&value!==null&&value!==false&&value!=='')return false
  return true
}
function sameContext(left:ModelContextSnapshot,right:ModelContextSnapshot):boolean{
  return left.id===right.id&&left.modelId===right.modelId&&left.modelRevision===right.modelRevision&&
    left.implementationFamily===right.implementationFamily&&left.selectionRevision===right.selectionRevision
}

/** Proposes a view from admitted execution only. Caller owns manual priority and lifecycle. */
export function selectThreadViewProposal({events,networkTasks,attemptId,currentContext}:{
  events:readonly EventEnvelope[];networkTasks:readonly ThreadNetworkTask[];attemptId:string|null|undefined;currentContext:ModelContextSnapshot|null|undefined
}):ThreadViewProposal|null{
  if(!text(attemptId))return null
  let proposal:ThreadViewProposal|null=null
  for(const event of events){
    if(event.visibility!=='public'||event.attemptId!==attemptId||event.eventType!=='runtime_event'||!sequence(event.eventSeq)||!successful(event.payload))continue
    const request=parseThreadDisplayRequest(event.payload.source_view)
    if(request&&(!proposal||event.eventSeq>proposal.eventSeq))proposal={kind:'source',eventSeq:event.eventSeq,attemptId,request}
  }
  if(currentContext)for(const task of networkTasks){
    // These tasks already passed Authority admission in ThreadProjectionStore.
    // Raw network_layer events never enter this selection path.
    if(task.presentationSource==='historical_baseline'||task.attemptId!==attemptId||!sequence(task.eventSeq)||!text(task.pageId)||!task.context||!sameContext(task.context,currentContext))continue
    const view=task.view
    if(view?.schema!=='capstone-network-view/2.0'||view.diagram?.schema!=='capstone-network-diagram/1.0'||
      view.diagram.model?.id!==currentContext.modelId||view.diagram.model.revision!==currentContext.modelRevision||
      view.layer?.diagram_ref!==view.diagram.ref||view.layer.model_revision!==currentContext.modelRevision||view.layer.ordinal!==view.ordinal)continue
    if(!proposal||task.eventSeq>proposal.eventSeq)proposal={kind:'model',eventSeq:task.eventSeq,attemptId,contextId:currentContext.id,pageId:task.pageId,view}
  }
  return proposal
}
