import {ELECTRICAL_STREAMS,type ElectricalRecords,type ElectricalViewReady,type ElectricalReadRequest} from './electricalModelView'
/** Small contract fixtures shared by focused parser and projection tests. */
export function electricalRecords():ElectricalRecords {return {
  devices:[{id:'device',kind:'breaker',name:'Breaker A',element_key:7,switch_position:{value:'closed',verified:false}}],
  ports:[{id:'p1',device_id:'device',identity_origin:'derived_incidence',role:null,sequence:null,source_slot:'FIRST_NODE_ID'},{id:'p2',device_id:'device',identity_origin:'source_terminal',role:null}],
  connectivity_nodes:[{id:'j1',kind:'connectivity_node',nominal_kv:110},{id:'j2',kind:'connectivity_node'}],
  connections:[{id:'c1',port_id:'p1',connectivity_node_id:'j1',kind:'source_connection'},{id:'c2',port_id:'p2',connectivity_node_id:'j2',kind:'source_connection'}],
  device_relations:[],groups:[{id:'station',kind:'station',name:'Station A',member_count:1,expand_target:'station'}],
  boundaries:[{id:'b1',device_id:'device',port_id:'p2',reason:'outside_partition'}],issues:[{id:'i1',code:'unknown_terminal_roles',subject_ref:'device'}],
}}
export function electricalManifest(records=electricalRecords(),target:string|null='station'):ElectricalViewReady {return {
  schema:'gateway-electrical-view/1',state:'ready',model_ref:'model:one',model_revision:'revision:1',view_ref:'view:station',source_snapshot_ref:'snapshot:1',selection_ref:'selection:1',representation:'source_node_breaker',target,
  streams:Object.fromEntries(ELECTRICAL_STREAMS.map(stream=>[stream,{total_count:records[stream].length}])) as ElectricalViewReady['streams'],
  capture:{read_started_at:1,read_completed_at:2,source_transaction_consistency_verified:false},readiness:'partial',readiness_scope:'structural_records_only; not power_flow_or_optimization',
}}
export function electricalPage(manifest:ElectricalViewReady,records:ElectricalRecords,request:ElectricalReadRequest){
  const offset=request.cursor?Number(request.cursor.split(':').at(-1)):0,items=records[request.stream].slice(offset,offset+(request.limit??200)),next=offset+items.length
  return {schema:manifest.schema,model_ref:manifest.model_ref,model_revision:manifest.model_revision,view_ref:manifest.view_ref,source_snapshot_ref:manifest.source_snapshot_ref,selection_ref:manifest.selection_ref,
    stream:request.stream,records:items,returned_count:items.length,total_count:records[request.stream].length,next_cursor:next<records[request.stream].length?`cursor:${request.stream}:${next}`:null,complete:next===records[request.stream].length}
}
