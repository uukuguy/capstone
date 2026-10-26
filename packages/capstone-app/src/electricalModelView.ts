/** Frozen gateway records. Structural readiness is not numerical readiness. */
export const ELECTRICAL_STREAMS=['devices','ports','connectivity_nodes','connections','device_relations','groups','boundaries','issues'] as const
export type ElectricalStream=typeof ELECTRICAL_STREAMS[number]
type RecordBase={id:string;[key:string]:unknown}
export type ElectricalDevice=RecordBase&{kind:string;name?:string|null;element_key?:string|number;station_refs?:string[];source_refs?:string[]}
export type ElectricalPort=RecordBase&{device_id:string;identity_origin:'source_terminal'|'derived_incidence'|'native_model';role:string|null;sequence?:number|null;source_slot?:string|null}
export type ElectricalNode=RecordBase&{kind:'connectivity_node'|'calculation_bus';name?:string|null;nominal_kv?:number|null}
export type ElectricalConnection=RecordBase&{port_id:string;connectivity_node_id:string;kind:'source_connection'|'native_model_endpoint'}
export type ElectricalRelation=RecordBase&{parent_id:string;child_id:string;kind:string;child_stream:'devices'|'ports';electrical_connection:false}
export type ElectricalGroup=RecordBase&{kind:'station';name?:string|null;member_count:number;expand_target:string}
export type ElectricalBoundary=RecordBase&{port_id:string;device_id:string;reason:'outside_partition'|'ownership_unknown'}
export type ElectricalIssue=RecordBase&{code:string;subject_ref:string|null}
export type ElectricalRecords={devices:ElectricalDevice[];ports:ElectricalPort[];connectivity_nodes:ElectricalNode[];connections:ElectricalConnection[];device_relations:ElectricalRelation[];groups:ElectricalGroup[];boundaries:ElectricalBoundary[];issues:ElectricalIssue[]}
type FrozenIdentity={schema:'gateway-electrical-view/1';model_ref:string;model_revision:string;view_ref:string;source_snapshot_ref?:string;selection_ref?:string}
export type ElectricalViewReady=FrozenIdentity&{state:'ready';representation:'source_node_breaker'|'calculation_bus_branch';streams:Record<ElectricalStream,{total_count:number;[key:string]:unknown}>;capture:Record<string,unknown>;target?:string|null;[key:string]:unknown}
export type ElectricalViewPreparing={schema:'gateway-electrical-view/1';state:'preparing';model_ref:string;preparation_ref:string;[key:string]:unknown}
export type ElectricalViewOpen=ElectricalViewReady|ElectricalViewPreparing
/** UI failure state, never a fabricated gateway manifest. */
export type ElectricalViewUnsupported={state:'unsupported';code:'unsupported_representation';retryable:false;recovery_action?:string}
export type ElectricalViewFailure=ElectricalViewUnsupported|{state:'error';code:string;retryable:boolean;recovery_action?:string}
export type ElectricalViewPage<S extends ElectricalStream=ElectricalStream>=FrozenIdentity&{stream:S;records:ElectricalRecords[S];returned_count:number;total_count:number;next_cursor:string|null;complete:boolean}
export type ElectricalReadRequest={view_ref:string;stream:ElectricalStream;cursor?:string;limit?:number}
export type ElectricalModelView={manifest:ElectricalViewReady;records:ElectricalRecords;loadedStreams:ElectricalStream[];complete:boolean}
export class ElectricalViewContractError extends Error {constructor(public readonly code:string){super(`电气视图数据无效：${code}`);this.name='ElectricalViewContractError'}}
function fail(code:string):never {throw new ElectricalViewContractError(code)}
const object=(value:unknown):Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:fail('object_required')
const string=(value:unknown):value is string=>typeof value==='string'&&value.length>0
const count=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
const optionalString=(row:Record<string,unknown>,key:string)=>{if(row[key]!==undefined&&row[key]!==null&&typeof row[key]!=='string')fail(`invalid_${key}`)}
const required=(row:Record<string,unknown>,...keys:string[])=>{for(const key of keys)if(!string(row[key]))fail(`invalid_${key}`)}
const identity=(row:Record<string,unknown>)=>{if(row.schema!=='gateway-electrical-view/1')fail('schema_mismatch');required(row,'model_ref','model_revision','view_ref');for(const key of ['source_snapshot_ref','selection_ref'])if(row[key]!==undefined&&!string(row[key]))fail(`invalid_${key}`)}

export function parseElectricalViewOpen(value:unknown):ElectricalViewOpen {
  const row=object(value)
  if(row.schema!=='gateway-electrical-view/1')fail('schema_mismatch')
  if(row.state==='preparing'){required(row,'model_ref','preparation_ref');return row as ElectricalViewPreparing}
  if(row.state!=='ready')fail('invalid_state')
  identity(row)
  if(!['source_node_breaker','calculation_bus_branch'].includes(String(row.representation)))fail('invalid_representation')
  object(row.capture);optionalString(row,'target')
  const streams=object(row.streams)
  for(const stream of ELECTRICAL_STREAMS)if(!count(object(streams[stream]).total_count))fail('invalid_stream_total')
  return row as ElectricalViewReady
}
export function parseElectricalViewFailure(value:unknown):ElectricalViewFailure|undefined {
  if(value===null||typeof value!=='object')return
  const envelope=value as Record<string,unknown>,detail=envelope.detail??envelope
  if(detail===null||typeof detail!=='object'||Array.isArray(detail))return
  const row=detail as Record<string,unknown>
  if(!string(row.code)||typeof row.retryable!=='boolean')return
  const recovery_action=typeof row.recovery_action==='string'?row.recovery_action:undefined
  return row.code==='unsupported_representation'?{state:'unsupported',code:row.code,retryable:false,recovery_action}:{state:'error',code:row.code,retryable:row.retryable,recovery_action}
}
function parseRecord(stream:ElectricalStream,value:unknown):RecordBase {
  const row=object(value);required(row,'id');optionalString(row,'name')
  for(const key of ['station_refs','source_refs','quality_refs'])if(row[key]!==undefined&&(!Array.isArray(row[key])||!(row[key] as unknown[]).every(string)))fail(`invalid_${key}`)
  if(row.element_key!==undefined&&typeof row.element_key!=='string'&&!(typeof row.element_key==='number'&&Number.isSafeInteger(row.element_key)))fail('invalid_element_key')
  switch(stream){
    case 'devices':required(row,'kind');break
    case 'ports':required(row,'device_id');if(!['source_terminal','derived_incidence','native_model'].includes(String(row.identity_origin))||!(row.role===null||typeof row.role==='string'))fail('invalid_port');if(row.sequence!==undefined&&row.sequence!==null&&!(typeof row.sequence==='number'&&Number.isSafeInteger(row.sequence)))fail('invalid_sequence');optionalString(row,'source_slot');break
    case 'connectivity_nodes':if(!['connectivity_node','calculation_bus'].includes(String(row.kind)))fail('invalid_node');if(row.nominal_kv!==undefined&&row.nominal_kv!==null&&!(typeof row.nominal_kv==='number'&&Number.isFinite(row.nominal_kv)))fail('invalid_voltage');break
    case 'connections':required(row,'port_id','connectivity_node_id');if(!['source_connection','native_model_endpoint'].includes(String(row.kind)))fail('invalid_connection');break
    case 'device_relations':required(row,'parent_id','child_id','kind');if(row.electrical_connection!==false||!['devices','ports'].includes(String(row.child_stream)))fail('invalid_membership');break
    case 'groups':required(row,'expand_target');if(row.kind!=='station'||!count(row.member_count))fail('invalid_group');break
    case 'boundaries':required(row,'port_id','device_id');if(!['outside_partition','ownership_unknown'].includes(String(row.reason)))fail('invalid_boundary');break
    case 'issues':required(row,'code');if(!(row.subject_ref===null||string(row.subject_ref)))fail('invalid_issue');break
  }
  return row as RecordBase
}
export function parseElectricalViewPage(value:unknown):ElectricalViewPage {
  const row=object(value);identity(row)
  if(!ELECTRICAL_STREAMS.includes(row.stream as ElectricalStream))fail('invalid_stream')
  if(!Array.isArray(row.records)||!count(row.returned_count)||row.returned_count>1000||row.returned_count!==row.records.length||!count(row.total_count)||row.total_count<row.returned_count)fail('invalid_page_counts')
  if(!(row.next_cursor===null||string(row.next_cursor))||typeof row.complete!=='boolean'||row.complete!==(row.next_cursor===null))fail('invalid_page_cursor')
  const seen=new Set<string>()
  for(const item of row.records){const record=parseRecord(row.stream as ElectricalStream,item);if(seen.has(record.id))fail('duplicate_record');seen.add(record.id)}
  return row as ElectricalViewPage
}
export function validateElectricalClosure(records:ElectricalRecords):void {
  const devices=new Set(records.devices.map(row=>row.id)),ports=new Set(records.ports.map(row=>row.id)),nodes=new Set(records.connectivity_nodes.map(row=>row.id)),owners=new Map(records.ports.map(row=>[row.id,row.device_id]))
  if(new Set([...devices,...ports,...nodes]).size!==devices.size+ports.size+nodes.size)fail('ambiguous_object_identity')
  for(const port of records.ports)if(!devices.has(port.device_id))fail('missing_port_device')
  for(const connection of records.connections)if(!ports.has(connection.port_id)||!nodes.has(connection.connectivity_node_id))fail('missing_connection_endpoint')
  for(const relation of records.device_relations)if(!devices.has(relation.parent_id)||!(relation.child_stream==='ports'?ports:devices).has(relation.child_id))fail('missing_relation_endpoint')
  for(const boundary of records.boundaries)if(!ports.has(boundary.port_id)||!devices.has(boundary.device_id)||owners.get(boundary.port_id)!==boundary.device_id)fail('invalid_boundary_endpoint')
}
export async function loadElectricalModelView(manifest:ElectricalViewReady,read:(request:ElectricalReadRequest,signal?:AbortSignal)=>Promise<unknown>,options:{mode:'groups'|'closure';signal?:AbortSignal;pageSize?:number;maxRecords?:number;maxPages?:number;onProgress?:(stream:ElectricalStream,loaded:number,total:number)=>void}):Promise<ElectricalModelView> {
  if(!options||!['groups','closure'].includes(options.mode))fail('explicit_read_mode_required')
  const ready=parseElectricalViewOpen(manifest);if(ready.state!=='ready')fail('view_not_ready')
  if(options.mode==='closure'&&!ready.target)fail('root_closure_requires_explicit_target')
  const streams:ElectricalStream[]=options.mode==='groups'?['groups']:[...ELECTRICAL_STREAMS],pageSize=options.pageSize??200,maxRecords=options.maxRecords??100000,maxPages=options.maxPages??2000
  if(!count(pageSize)||pageSize<1||pageSize>1000||!count(maxRecords)||!count(maxPages)||maxPages<1)fail('invalid_read_budget')
  if(streams.reduce((sum,stream)=>sum+ready.streams[stream].total_count,0)>maxRecords)fail('view_budget_exceeded')
  const records:ElectricalRecords={devices:[],ports:[],connectivity_nodes:[],connections:[],device_relations:[],groups:[],boundaries:[],issues:[]}
  const abort=()=>{if(options.signal?.aborted)throw new DOMException('Aborted','AbortError')}
  let pages=0
  for(const stream of streams){
    const ids=new Set<string>(),cursors=new Set<string>();let cursor:string|undefined
    do {
      abort();if(++pages>maxPages)fail('page_budget_exceeded')
      const value=await read({view_ref:ready.view_ref,stream,limit:pageSize,...(cursor?{cursor}:{})},options.signal);abort();const page=parseElectricalViewPage(value)
      for(const field of ['model_ref','model_revision','view_ref','source_snapshot_ref','selection_ref'] as const)if(page[field]!==ready[field])fail('frozen_baseline_mismatch')
      if(page.stream!==stream||page.total_count!==ready.streams[stream].total_count||page.returned_count>pageSize)fail('stream_manifest_mismatch')
      for(const record of page.records){if(ids.has(record.id))fail('duplicate_record');ids.add(record.id);(records[stream] as RecordBase[]).push(record)}
      if(ids.size>page.total_count||page.complete&&ids.size!==page.total_count||!page.complete&&(!page.returned_count||ids.size>=page.total_count))fail('incomplete_stream')
      if(page.next_cursor!==null){if(cursors.has(page.next_cursor))fail('cursor_cycle');cursors.add(page.next_cursor)}
      options.onProgress?.(stream,ids.size,page.total_count);cursor=page.next_cursor??undefined
    }while(cursor)
  }
  abort();if(options.mode==='closure')validateElectricalClosure(records)
  return {manifest:ready,records,loadedStreams:streams,complete:true}
}
