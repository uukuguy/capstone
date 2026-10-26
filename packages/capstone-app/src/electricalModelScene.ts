import {ELECTRICAL_STREAMS,ElectricalViewContractError,validateElectricalClosure,type ElectricalModelView,type ElectricalDevice} from './electricalModelView'
import type {NetworkScene,NetworkSceneNode,NetworkSceneEdge,SceneDetail} from './networkScene'

const text=(value:unknown)=>typeof value==='string'?value:undefined
function details(record:{id:string;[key:string]:unknown}):SceneDetail[]{
  const result:SceneDetail[]=[{label:'源记录',value:record.id}]
  if(typeof record.legacy_object_ref==='string')result.push({label:'兼容对象引用',value:record.legacy_object_ref})
  if(record.element_key!==undefined)result.push({label:'引擎元素键',value:`${typeof record.element_key}: ${String(record.element_key)}`})
  return result
}
function switchState(device:ElectricalDevice):'open'|'closed'|'unknown'|undefined {
  if(!['breaker','breakers','disconnector','disconnectors','switch','ground_disconnector','ground_disconnectors'].includes(device.kind))return
  const state=device.switch_position
  if(state&&typeof state==='object'&&!Array.isArray(state)){
    const row=state as Record<string,unknown>
    if(row.verified===true&&(row.value==='open'||row.value==='closed'))return row.value
  }
  return 'unknown'
}
/** Connections terminate at published port identities, never directly at devices. */
export function electricalModelScene(view:ElectricalModelView):NetworkScene {
  if(!view.complete)throw new ElectricalViewContractError('incomplete_view')
  if(view.loadedStreams.length===1&&view.loadedStreams[0]==='groups')return {
    ref:view.manifest.view_ref,coordinateSystem:'schematic',displayMode:'source-regional',edges:[],
    nodes:view.records.groups.map(group=>({id:group.id,label:group.name||group.id,showLabel:!!group.name?.trim()&&group.name!==group.id,kind:'station',sourceRef:group.id,details:[...details(group),{label:'分组',value:'源站点目录；不代表电气等值母线'},{label:'成员数',value:String(group.member_count)}]})),
  }
  if(!ELECTRICAL_STREAMS.every(stream=>view.loadedStreams.includes(stream)))throw new ElectricalViewContractError('incomplete_closure')
  validateElectricalClosure(view.records)
  const {devices,ports,connectivity_nodes,connections,device_relations,boundaries}=view.records
  const boundaryIds=new Set(boundaries.flatMap(row=>[row.port_id,row.device_id]))
  const counts=new Map<string,Set<string>>(),deviceKinds=new Map(devices.map(device=>[device.id,device.kind]))
  for(const relation of device_relations)if(relation.child_stream==='devices'&&['winding','windings'].includes(deviceKinds.get(relation.child_id)||'')){
    const children=counts.get(relation.parent_id)||new Set<string>();children.add(relation.child_id);counts.set(relation.parent_id,children)
  }
  const nodes:NetworkSceneNode[]=[
    ...devices.map(device=>({id:device.id,label:device.name||device.id,showLabel:!!device.name?.trim()&&device.name!==device.id,kind:device.kind,sourceRef:device.id,
      stationId:device.station_refs?.length===1?device.station_refs[0]:undefined,boundary:boundaryIds.has(device.id),switchState:switchState(device),
      symbolKind:['transformer','transformers'].includes(device.kind)&&counts.get(device.id)?.size===3?'trafo3w':undefined,details:details(device)})),
    ...ports.map(port=>({id:port.id,label:port.id,showLabel:false,kind:'port',symbolKind:'terminal',parentId:port.device_id,sourceRef:port.id,boundary:boundaryIds.has(port.id),
      details:[...details(port),{label:'所属设备',value:port.device_id},{label:'身份来源',value:port.identity_origin},{label:'端子角色',value:port.role??'未核准'},...(port.sequence===undefined||port.sequence===null?[]:[{label:'端序',value:String(port.sequence)}]),...(port.source_slot?[{label:'源字段槽位',value:port.source_slot}]:[])]})),
    ...connectivity_nodes.map(node=>({id:node.id,label:node.name||node.id,showLabel:false,kind:node.kind==='calculation_bus'?'bus':'connection_node',sourceRef:node.id,voltageKv:node.nominal_kv,
      details:[...details(node),{label:'记录类型',value:node.kind},...(text(node.voltage_origin)?[{label:'电压来源',value:text(node.voltage_origin)!}]:[])]})),
  ]
  const edges:NetworkSceneEdge[]=[
    ...connections.map(connection=>({id:connection.id,source:connection.port_id,target:connection.connectivity_node_id,kind:connection.kind,relation:'connection' as const,sourceRef:connection.id,details:details(connection)})),
    ...device_relations.map(relation=>({id:relation.id,source:relation.parent_id,target:relation.child_id,kind:relation.kind,relation:'membership' as const,sourceRef:relation.id,details:[...details(relation),{label:'关系',value:'设备构成；非导通边'}]})),
  ]
  const declaredOwnership=new Set(device_relations.filter(relation=>relation.child_stream==='ports').map(relation=>JSON.stringify([relation.parent_id,relation.child_id])))
  for(const port of ports)if(!declaredOwnership.has(JSON.stringify([port.device_id,port.id])))edges.push({
    id:`display:port-owner:${port.id}`,source:port.device_id,target:port.id,kind:'port_ownership',relation:'membership',sourceRef:port.id,
    details:[{label:'关系',value:'端口归属；非导通边'},{label:'投影依据',value:'ports.device_id'},{label:'源端口',value:port.id}],
  })
  const ids=new Set<string>()
  for(const item of [...nodes,...edges]){if(ids.has(item.id))throw new ElectricalViewContractError('ambiguous_scene_identity');ids.add(item.id)}
  return {ref:view.manifest.view_ref,coordinateSystem:'schematic',displayMode:'source-electrical',nodes,edges}
}
